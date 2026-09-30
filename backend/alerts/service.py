import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.alerts import models, schemas, change_detector, evaluator, templates, power_automate


def get_or_create_config(db: Session) -> models.AlertConfiguration:
    cfg = db.query(models.AlertConfiguration).first()
    if not cfg:
        cfg = models.AlertConfiguration(
            power_automate_webhook_url="",
            secret_header_name="X-WSA-Secret-Token",
            secret_header_value="",
            dashboard_base_url="http://localhost:8000",
            poll_interval_seconds=60,
            alerts_paused=False,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def resolve_rule_recipients(
    db: Session,
    rule: models.AlertRule,
    matched_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolves active To, CC, and BCC email addresses and group display names for a rule.
    Deduplicates addresses while preserving order.
    """
    to_emails: List[str] = []
    cc_emails: List[str] = []
    bcc_emails: List[str] = []
    to_group_names: List[str] = []
    cc_group_names: List[str] = []

    for assign in rule.recipient_assignments or []:
        rtype = (assign.recipient_type or "TO").upper()
        target_list = to_emails if rtype == "TO" else (cc_emails if rtype == "CC" else bcc_emails)

        if assign.group_id and assign.group and assign.group.is_active:
            if rtype == "TO" and assign.group.name not in to_group_names:
                to_group_names.append(assign.group.name)
            elif rtype == "CC" and assign.group.name not in cc_group_names:
                cc_group_names.append(assign.group.name)

            for m in assign.group.memberships or []:
                if m.recipient and m.recipient.is_active and m.recipient.email:
                    email_clean = m.recipient.email.strip()
                    if email_clean and email_clean not in target_list:
                        target_list.append(email_clean)

        if assign.email_address:
            for raw_e in assign.email_address.split(","):
                e_clean = raw_e.strip()
                if e_clean and "@" in e_clean and e_clean not in target_list:
                    target_list.append(e_clean)

        if assign.dynamic_field and matched_records:
            for rec in matched_records:
                val = str(rec.get(assign.dynamic_field, "") or "").strip()
                if "@" in val and val not in target_list:
                    target_list.append(val)

    return {
        "to": to_emails,
        "cc": cc_emails,
        "bcc": bcc_emails,
        "to_group_names": to_group_names,
        "cc_group_names": cc_group_names,
    }


def compute_event_fingerprint(
    rule: models.AlertRule,
    matched_records: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> str:
    """
    Computes a deterministic idempotency fingerprint for (rule_id + triggering records / group).
    Prevents duplicate emails for the same Excel record or same group window.
    """
    record_keys = sorted(r.get("record_key", "") for r in matched_records if r.get("record_key"))
    raw_key = json.dumps(
        {
            "rule_id": rule.id,
            "trigger_type": rule.trigger_type,
            "station": summary.get("station", ""),
            "date": summary.get("date", ""),
            "record_keys": record_keys[:20],
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def is_duplicate_or_in_cooldown(
    db: Session,
    rule: models.AlertRule,
    fingerprint: str,
) -> Tuple[bool, str]:
    """
    Checks if:
      1. The exact same event fingerprint was already triggered for this rule (idempotency), OR
      2. The rule is still within its configured cooldown window.
    """
    existing_fp = (
        db.query(models.AlertEvent)
        .filter(
            models.AlertEvent.rule_id == rule.id,
            models.AlertEvent.fingerprint == fingerprint,
            models.AlertEvent.event_type == "PRODUCTION",
        )
        .order_by(models.AlertEvent.triggered_at.desc())
        .first()
    )
    if existing_fp:
        if not rule.cooldown_minutes or rule.cooldown_minutes <= 0:
            return True, f"Identical event fingerprint already triggered at {existing_fp.triggered_at.strftime('%Y-%m-%d %H:%M')}"
        elapsed = datetime.utcnow() - existing_fp.triggered_at
        if elapsed < timedelta(minutes=rule.cooldown_minutes):
            return True, f"Duplicate event suppressed by {rule.cooldown_minutes}m cooldown"

    if rule.cooldown_minutes and rule.cooldown_minutes > 0:
        last_event = (
            db.query(models.AlertEvent)
            .filter(
                models.AlertEvent.rule_id == rule.id,
                models.AlertEvent.event_type == "PRODUCTION",
            )
            .order_by(models.AlertEvent.triggered_at.desc())
            .first()
        )
        if last_event:
            elapsed = datetime.utcnow() - last_event.triggered_at
            if elapsed < timedelta(minutes=rule.cooldown_minutes):
                remaining = int((timedelta(minutes=rule.cooldown_minutes) - elapsed).total_seconds() // 60) + 1
                return True, f"Rule on cooldown ({remaining}m remaining)"

    return False, ""


def collect_all_normalized_records(investigation_records: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Loads and normalizes records from both WSA Particle Summary and Investigation Dashboard."""
    unified: List[Dict[str, Any]] = []

    # 1. Particle Summary records
    ps_raw = change_detector.load_particle_summary_records()
    for r in ps_raw:
        unified.append(change_detector.normalize_unified_record(r))

    # 2. Investigation Dashboard records
    if investigation_records is None:
        try:
            from backend.investigation_loader import get_cached_investigation_data
            inv_data = get_cached_investigation_data()
            investigation_records = inv_data.get("records", [])
        except Exception:
            investigation_records = []

    for r in investigation_records or []:
        unified.append(change_detector.normalize_unified_record(r))

    return unified


def create_event_and_delivery(
    db: Session,
    rule: models.AlertRule,
    reason: str,
    matched_records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    fingerprint: str,
    is_test: bool = False,
) -> Tuple[models.AlertEvent, models.AlertDelivery]:
    cfg = get_or_create_config(db)
    base_url = (cfg.dashboard_base_url or "http://localhost:8000").rstrip("/")
    dashboard_url = f"{base_url}/observations"

    resolved_recips = resolve_rule_recipients(db, rule, matched_records)
    tmpl = rule.template
    if not tmpl:
        tmpl = db.query(models.EmailTemplate).filter(models.EmailTemplate.is_default == True).first()

    rendered = templates.render_alert_email(
        rule=rule,
        template=tmpl,
        summary=summary,
        matched_records=matched_records,
        dashboard_url=dashboard_url,
        trigger_reason=reason,
    )

    now = datetime.utcnow()
    evt_uuid = f"evt_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

    clean_matched = [
        {k: v for k, v in r.items() if k not in ("raw", "_row_hash")}
        for r in matched_records[:10]
    ]

    event = models.AlertEvent(
        event_uuid=evt_uuid,
        fingerprint=fingerprint,
        rule_id=rule.id,
        rule_name_snapshot=rule.name,
        trigger_type=rule.trigger_type,
        severity=rule.severity,
        event_type="TEST" if is_test else "PRODUCTION",
        station=summary.get("station", ""),
        customer=summary.get("customer", ""),
        shift=summary.get("shift", ""),
        trigger_reason=reason,
        context_json=json.dumps({"summary": summary, "matched_records": clean_matched}),
        triggered_at=now,
    )
    db.add(event)
    db.flush()

    if not is_test:
        rule.last_triggered_at = now

    delivery = models.AlertDelivery(
        event_id=event.id,
        channel="POWER_AUTOMATE",
        status="QUEUED",
        recipients_to_json=json.dumps(resolved_recips["to"]),
        recipients_cc_json=json.dumps(resolved_recips["cc"]),
        recipients_bcc_json=json.dumps(resolved_recips["bcc"]),
        rendered_subject=rendered["subject"],
        rendered_body_html=rendered["body_html"],
        retry_count=0,
        max_retries=rule.max_retries or 3,
    )
    db.add(delivery)
    db.flush()

    pa_payload = schemas.PowerAutomatePayload(
        event_id=evt_uuid,
        delivery_id=delivery.id,
        is_test=is_test,
        rule_id=rule.id,
        rule_name=rule.name,
        rule_category=rule.rule_category or "EVENT",
        trigger_type=rule.trigger_type,
        severity=rule.severity,
        triggered_at=now.isoformat(),
        date=str(summary.get("date", "")),
        shift=str(summary.get("shift", "")),
        station=str(summary.get("station", "")),
        auditor=str(summary.get("auditor", "")),
        customer=str(summary.get("customer", "")),
        injector_type=str(summary.get("injector_type", "")),
        parts_checked=float(summary.get("parts_checked", 0) or 0),
        nok_count=int(summary.get("nok_count", 0) or 0),
        nok_rate=float(summary.get("nok_rate", 0.0) or 0.0),
        total_particles=float(summary.get("total_particles", 0) or 0),
        particle_location=str(summary.get("particle_location", "")),
        chemistry=str(summary.get("chemistry", "")),
        size=str(summary.get("size", "")),
        rejection_date=str(summary.get("rejection_date", "")),
        rejection_shift=str(summary.get("rejection_shift", "")),
        observation=rendered["observation"],
        required_action=rendered["required_action"],
        dashboard_url=dashboard_url,
        recipients=resolved_recips["to"],
        cc_recipients=resolved_recips["cc"],
        bcc_recipients=resolved_recips["bcc"],
        email_subject=rendered["subject"],
        email_body_html=rendered["body_html"],
        matched_records=clean_matched,
    ).model_dump()

    delivery.payload_json = json.dumps(pa_payload)
    db.commit()
    db.refresh(event)
    db.refresh(delivery)

    # Attempt immediate Power Automate webhook delivery if URL is configured
    power_automate.attempt_delivery(db, delivery, rule)
    return event, delivery


def run_evaluation_cycle(
    db: Session,
    force_evaluate_all: bool = False,
    include_scheduled: bool = False,
    investigation_records: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Runs a full change-detection + rule-evaluation cycle.
    Safe to call on `/refresh-data`, background scheduler ticks, or manual Admin evaluation.
    """
    cfg = get_or_create_config(db)
    cfg.last_evaluation_at = datetime.utcnow()
    db.commit()

    if cfg.alerts_paused and not force_evaluate_all:
        return {"status": "paused", "events_created": 0, "changes_detected": 0}

    all_records = collect_all_normalized_records(investigation_records)
    diff = change_detector.detect_and_sync_changes(
        db,
        all_records,
        seed_as_baseline_if_empty=not force_evaluate_all,
    )

    candidate_records = (
        all_records
        if force_evaluate_all
        else (diff["added"] + diff["updated"])
    )

    query = db.query(models.AlertRule).filter(models.AlertRule.is_enabled == True)
    if not include_scheduled and not force_evaluate_all:
        query = query.filter(models.AlertRule.rule_category == "EVENT")

    active_rules = query.order_by(models.AlertRule.priority.asc(), models.AlertRule.id.asc()).all()
    created_events: List[int] = []
    suppressed_count = 0

    for rule in active_rules:
        triggered, reason, matched, summary = evaluator.evaluate_rule(
            rule=rule,
            candidate_records=candidate_records,
            all_records=all_records,
            is_test=False,
        )
        if not triggered:
            continue

        fp = compute_event_fingerprint(rule, matched, summary)
        is_dup, suppress_reason = is_duplicate_or_in_cooldown(db, rule, fp)
        if is_dup:
            suppressed_count += 1
            continue

        evt, _ = create_event_and_delivery(
            db=db,
            rule=rule,
            reason=reason,
            matched_records=matched,
            summary=summary,
            fingerprint=fp,
            is_test=False,
        )
        created_events.append(evt.id)

    return {
        "status": "completed",
        "total_records_scanned": len(all_records),
        "changes_detected": len(diff["added"]) + len(diff["updated"]),
        "is_baseline_seed": diff["is_baseline_seed"],
        "events_created": len(created_events),
        "event_ids": created_events,
        "suppressed_by_cooldown_or_dedup": suppressed_count,
    }


def run_rule_test_preview(
    db: Session,
    rule: models.AlertRule,
    record_test_event: bool = False,
) -> Dict[str, Any]:
    """
    Executes a safe dry-run / test of a rule against current WSA data.
    Shows evaluated conditions, resulting data, recipients, rendered HTML email,
    and optional test delivery without creating a production alert event.
    """
    all_records = collect_all_normalized_records()
    triggered, reason, matched, summary = evaluator.evaluate_rule(
        rule=rule,
        candidate_records=all_records,
        all_records=all_records,
        is_test=True,
    )

    # Even if 0 records matched the strict condition in current Excel, provide a realistic preview specimen
    if not matched:
        sample_pool = [r for r in all_records if r.get("status") == "NOK"] or all_records[:5]
        summary = evaluator.compute_pool_summary(sample_pool)

    resolved_recips = resolve_rule_recipients(db, rule, matched)
    cfg = get_or_create_config(db)
    dashboard_url = f"{(cfg.dashboard_base_url or 'http://localhost:8000').rstrip('/')}/observations"

    tmpl = rule.template or db.query(models.EmailTemplate).filter(models.EmailTemplate.is_default == True).first()
    rendered = templates.render_alert_email(
        rule=rule,
        template=tmpl,
        summary=summary,
        matched_records=matched,
        dashboard_url=dashboard_url,
        trigger_reason=reason or f"Test evaluation for rule '{rule.name}'",
    )

    human_summary = evaluator.build_human_readable_summary(
        rule,
        resolved_recips["to_group_names"],
        resolved_recips["cc_group_names"],
    )

    delivery_status = "DRY_RUN_PREVIEW"
    delivery_id = None
    if record_test_event:
        fp = f"TEST_{uuid.uuid4().hex[:10]}"
        _, deliv = create_event_and_delivery(
            db=db,
            rule=rule,
            reason=f"[TEST ALERT] {reason}",
            matched_records=matched,
            summary=summary,
            fingerprint=fp,
            is_test=True,
        )
        delivery_status = deliv.status
        delivery_id = deliv.id

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "severity": rule.severity,
        "human_readable_summary": human_summary,
        "condition_matched_current_data": triggered,
        "evaluation_reason": reason,
        "matched_record_count": len(matched),
        "summary_data": summary,
        "recipients": resolved_recips,
        "rendered_email": rendered,
        "delivery_status": delivery_status,
        "delivery_id": delivery_id,
    }


def process_pending_retries(db: Session) -> int:
    """Checks for queued/failed deliveries due for retry and attempts webhook dispatch."""
    now = datetime.utcnow()
    due_deliveries = (
        db.query(models.AlertDelivery)
        .filter(
            models.AlertDelivery.status == "QUEUED",
            models.AlertDelivery.next_retry_at != None,
            models.AlertDelivery.next_retry_at <= now,
        )
        .all()
    )
    retried = 0
    for d in due_deliveries:
        rule = d.event.rule if d.event else None
        power_automate.attempt_delivery(db, d, rule)
        retried += 1
    return retried
