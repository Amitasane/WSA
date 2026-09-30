import json
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.alerts import (
    models,
    change_detector,
    evaluator,
    templates,
    service,
    power_automate,
    bootstrap,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        bootstrap.ensure_alert_system_initialized(db)
        # Clear baseline snapshots seeded from local disk so unit tests control their own dataset
        db.query(models.DataRecordSnapshot).delete()
        db.commit()
        yield db
    finally:
        db.close()


def _sample_wsa_records():
    return [
        change_detector.normalize_unified_record({
            "data_source": "PARTICLE_SUMMARY",
            "row_number": 2,
            "Date": "17-09-2026",
            "_date_iso": "2026-09-17",
            "Shift": "1st",
            "Auditor": "Shravani Pawar",
            "Type": "0445120568",
            "Customer": "TML",
            "Station": "EMI",
            "Defective parts checked": 48,
            "Particle inside nozzle": 0,
            "Particle in Z hole": 1,
            "Particle in A hole": 0,
            "Total particle found": 1,
            "Rejection Date": "16-09-2026",
            "Rejection Shift": "2nd",
            "Metallic/Non metallic": "Metallic",
            "DA/Fresh": "Fresh",
            "Chemistry": "FeCr",
            "Size": "420 um",
            "status": "NOK",
        }),
        change_detector.normalize_unified_record({
            "data_source": "PARTICLE_SUMMARY",
            "row_number": 3,
            "Date": "18-09-2026",
            "_date_iso": "2026-09-18",
            "Shift": "1st",
            "Auditor": "Shravani Pawar",
            "Type": "0445120568",
            "Customer": "TML",
            "Station": "EMI",
            "Defective parts checked": 30,
            "Particle inside nozzle": 0,
            "Particle in Z hole": 0,
            "Particle in A hole": 0,
            "Total particle found": 0,
            "Rejection Date": "",
            "Rejection Shift": "",
            "Metallic/Non metallic": "",
            "DA/Fresh": "Fresh",
            "Chemistry": "",
            "Size": "",
            "status": "OK",
        }),
    ]


def test_and_or_conditions_and_thresholds():
    records = _sample_wsa_records()

    # AND rule: Status == NOK AND Particle Location contains 'Z hole' AND Total particle found >= 1
    rule_and = models.AlertRule(
        name="Z-Hole Critical",
        trigger_type="PARTICLE_LOCATION",
        logical_operator="AND",
        conditions=[
            models.AlertCondition(field_name="Status", operator="eq", value="NOK"),
            models.AlertCondition(field_name="Particle Location", operator="contains", value="Z hole"),
            models.AlertCondition(field_name="Total particle found", operator="gte", value="1"),
        ],
    )
    triggered, reason, matched, summary = evaluator.evaluate_rule(rule_and, records, records)
    assert triggered is True
    assert len(matched) == 1
    assert summary["station"] == "EMI"
    assert summary["particle_location"] == "Z hole"

    # OR rule: Station == QMM99 OR Customer == TML
    rule_or = models.AlertRule(
        name="Station OR Customer",
        trigger_type="NOK_DETECTED",
        logical_operator="OR",
        conditions=[
            models.AlertCondition(field_name="Station", operator="eq", value="QMM99"),
            models.AlertCondition(field_name="Customer", operator="eq", value="TML"),
        ],
    )
    triggered_or, _, matched_or, _ = evaluator.evaluate_rule(rule_or, records, records)
    assert triggered_or is True
    assert len(matched_or) == 1


def test_repeated_nok_window_and_rate_threshold():
    recs = _sample_wsa_records()
    # Add second NOK at same station EMI
    recs.append(
        change_detector.normalize_unified_record({
            "data_source": "PARTICLE_SUMMARY",
            "row_number": 4,
            "Date": "17-09-2026",
            "_date_iso": "2026-09-17",
            "Shift": "2nd",
            "Station": "EMI",
            "Defective parts checked": 12,
            "Particle in Z hole": 1,
            "Total particle found": 1,
            "status": "NOK",
        })
    )

    rep_rule = models.AlertRule(
        name="Repeated EMI NOK >= 2",
        trigger_type="REPEATED_NOK_WINDOW",
        threshold_value=2.0,
        time_window_hours=4.0,
        group_by_field="Station",
        conditions=[models.AlertCondition(field_name="Status", operator="eq", value="NOK")],
    )
    triggered, reason, matched, summary = evaluator.evaluate_rule(rep_rule, recs, recs)
    assert triggered is True
    assert len(matched) == 2
    assert "2 NOK records" in reason

    # NOK Rate threshold test (2 NOK records over 90 total parts = 2.22% > 2.0%)
    rate_rule = models.AlertRule(
        name="Station NOK Rate > 2%",
        trigger_type="NOK_RATE_THRESHOLD",
        threshold_value=2.0,
        group_by_field="Station",
    )
    trig_rate, reason_rate, _, sum_rate = evaluator.evaluate_rule(rate_rule, recs, recs)
    assert trig_rate is True
    assert sum_rate["nok_rate"] >= 2.0


def test_data_change_detection_and_excel_refresh_idempotency(db_session):
    recs = _sample_wsa_records()

    # 1. Initial baseline seed: should record snapshots without emitting 'added' changes
    diff1 = change_detector.detect_and_sync_changes(db_session, recs, seed_as_baseline_if_empty=True)
    assert diff1["is_baseline_seed"] is True
    assert len(diff1["added"]) == 0

    # 2. Repeated refresh with identical Excel data: 0 changes
    diff2 = change_detector.detect_and_sync_changes(db_session, recs, seed_as_baseline_if_empty=True)
    assert diff2["is_baseline_seed"] is False
    assert len(diff2["added"]) == 0
    assert len(diff2["updated"]) == 0

    # 3. New NOK row added to Excel: detected once
    new_row = change_detector.normalize_unified_record({
        "data_source": "PARTICLE_SUMMARY",
        "row_number": 99,
        "Date": "19-09-2026",
        "_date_iso": "2026-09-19",
        "Shift": "1st",
        "Station": "FMI",
        "Defective parts checked": 24,
        "Particle in Z hole": 2,
        "Total particle found": 2,
        "status": "NOK",
    })
    recs_plus = recs + [new_row]
    diff3 = change_detector.detect_and_sync_changes(db_session, recs_plus, seed_as_baseline_if_empty=True)
    assert len(diff3["added"]) == 1
    assert len(diff3["status_changed_to_nok"]) == 1
    assert diff3["added"][0]["station"] == "FMI"


def test_recipient_groups_and_bosch_template_rendering(db_session):
    rule = db_session.query(models.AlertRule).filter(models.AlertRule.rule_category == "EVENT").first()
    recs = _sample_wsa_records()
    resolved = service.resolve_rule_recipients(db_session, rule, recs)

    assert len(resolved["to"]) > 0
    assert len(resolved["cc"]) > 0
    assert "Shums.Tabrez@de.bosch.com" in resolved["to"] or "Manoj.Patil@in.bosch.com" in resolved["to"]
    assert "Ramesh.Saligrama@in.bosch.com" in resolved["cc"]

    summary = evaluator.compute_pool_summary([recs[0]])
    rendered = templates.render_alert_email(
        rule=rule,
        template=rule.template,
        summary=summary,
        matched_records=[recs[0]],
        dashboard_url="http://localhost:8080/observations",
        trigger_reason="Particle observed at Z hole",
    )
    assert "CRIN - Line 5 internal rejection analysis MIS" in rendered["subject"]
    assert "Z hole" in rendered["body_html"]
    assert "0445120568" in rendered["body_html"]


def test_end_to_end_pipeline_deduplication_and_retries(db_session, monkeypatch):
    recs = _sample_wsa_records()
    rule = db_session.query(models.AlertRule).filter(models.AlertRule.priority == 1).first()
    rule.cooldown_minutes = 60
    db_session.commit()

    # Step 1: Evaluate rule -> create event & delivery -> verify Power Automate payload
    triggered, reason, matched, summary = evaluator.evaluate_rule(rule, [recs[0]], recs)
    assert triggered is True

    fp = service.compute_event_fingerprint(rule, matched, summary)
    is_dup, _ = service.is_duplicate_or_in_cooldown(db_session, rule, fp)
    assert is_dup is False

    event, delivery = service.create_event_and_delivery(
        db=db_session,
        rule=rule,
        reason=reason,
        matched_records=matched,
        summary=summary,
        fingerprint=fp,
        is_test=False,
    )
    assert event.id is not None
    assert delivery.status == "QUEUED"

    payload = json.loads(delivery.payload_json)
    assert payload["event_id"] == event.event_uuid
    assert payload["severity"] == "CRITICAL"
    assert payload["station"] == "EMI"
    assert payload["particle_location"] == "Z hole"
    assert len(payload["recipients"]) > 0

    # Step 2: Verify duplicate / cooldown guard blocks second identical trigger
    is_dup_after, suppress_msg = service.is_duplicate_or_in_cooldown(db_session, rule, fp)
    assert is_dup_after is True

    # Step 3: Simulate failed webhook attempt -> verify retry increment and next_retry_at
    cfg = service.get_or_create_config(db_session)
    cfg.power_automate_webhook_url = "https://example.invalid/webhook"
    db_session.commit()

    monkeypatch.setattr(
        power_automate,
        "send_webhook_payload",
        lambda *args, **kwargs: (False, 502, "Bad Gateway from Flow"),
    )
    ok = power_automate.attempt_delivery(db_session, delivery, rule)
    assert ok is False
    assert delivery.retry_count == 1
    assert delivery.next_retry_at is not None
    assert delivery.http_status_code == 502
    assert "Bad Gateway" in delivery.error_message

    # Step 4: Simulate successful retry -> verify DELIVERED status and timestamp
    monkeypatch.setattr(
        power_automate,
        "send_webhook_payload",
        lambda *args, **kwargs: (True, 202, "Accepted"),
    )
    ok2 = power_automate.attempt_delivery(db_session, delivery, rule)
    assert ok2 is True
    assert delivery.status == "DELIVERED"
    assert delivery.delivered_at is not None


def test_scheduled_summary_and_test_isolation(db_session):
    sched_rule = (
        db_session.query(models.AlertRule)
        .filter(models.AlertRule.trigger_type == "DAILY_SUMMARY")
        .first()
    )
    assert sched_rule is not None

    # Run test preview and verify it does not create a PRODUCTION event
    preview = service.run_rule_test_preview(db_session, sched_rule, record_test_event=True)
    assert preview["rule_id"] == sched_rule.id
    assert "CRIN - Line 5" in preview["rendered_email"]["subject"]

    prod_events = (
        db_session.query(models.AlertEvent)
        .filter(models.AlertEvent.event_type == "PRODUCTION")
        .count()
    )
    test_events = (
        db_session.query(models.AlertEvent)
        .filter(models.AlertEvent.event_type == "TEST")
        .count()
    )
    assert prod_events == 0
    assert test_events == 1


def test_admin_permissions_and_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # Unauthenticated request to /admin/alerts redirects to /login
    resp_unauth = client.get("/admin/alerts", follow_redirects=False)
    assert resp_unauth.status_code in (302, 307)
    assert "/login" in resp_unauth.headers.get("location", "")

    # Poll endpoint returns valid JSON list for Power Automate
    resp_poll = client.post("/api/alerts/poll")
    assert resp_poll.status_code == 200
    assert isinstance(resp_poll.json(), list)

