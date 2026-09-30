import json
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.alerts import (
    models,
    schemas,
    service,
    evaluator,
    templates as tmpl_engine,
    power_automate,
    bootstrap,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

TRIGGER_TYPE_OPTIONS = [
    ("NOK_DETECTED", "NOK / Rejection Detected (EVENT)"),
    ("FIRST_NOK_OF_DAY", "First NOK of the Day (EVENT)"),
    ("PARTICLE_FOUND", "Particle Contamination Found (EVENT)"),
    ("PARTICLE_LOCATION", "Particle Found at Specific Location e.g. Z-Hole (EVENT)"),
    ("PARTICLE_COUNT_THRESHOLD", "Particle Count Exceeds Threshold (EVENT)"),
    ("STATION_NOK", "Specific Station Produces NOK (EVENT)"),
    ("AUDITOR_NOK", "Specific Auditor Records NOK (EVENT)"),
    ("CUSTOMER_NOK", "Specific Customer / Type Generates NOK (EVENT)"),
    ("NOK_COUNT_THRESHOLD", "NOK Count Exceeds Threshold (EVENT)"),
    ("REPEATED_NOK_WINDOW", "Repeated NOK Within Time Window (EVENT)"),
    ("NOK_RATE_THRESHOLD", "NOK Rate (%) Exceeds Threshold (EVENT)"),
    ("SUDDEN_SPIKE", "Sudden Increase / Spike vs Baseline (EVENT)"),
    ("DAILY_SUMMARY", "Daily Analysis MIS Summary (SCHEDULED)"),
    ("SHIFT_SUMMARY", "End-of-Shift Analysis Summary (SCHEDULED)"),
    ("MISSING_UPDATE_DEADLINE", "No Analysis / Update Received by Deadline (SCHEDULED)"),
    ("ACTION_PLAN_FOLLOWUP", "Gemba / Action-Plan Follow-Up Reminder (SCHEDULED)"),
    ("PENDING_INVESTIGATION_AGE", "Pending Investigation Beyond X Days (SCHEDULED)"),
    ("CUSTOM_COMPOSITE", "Custom Composite Condition Rule (EVENT)"),
]

DATA_FIELD_OPTIONS = [
    "Status",
    "Station",
    "Particle Location",
    "Total particle found",
    "Particle in Z hole",
    "Particle inside nozzle",
    "Particle in A hole",
    "Defective parts checked",
    "Shift",
    "Rejection Shift",
    "Customer",
    "Type",
    "Auditor",
    "Metallic/Non metallic",
    "DA/Fresh",
    "Chemistry",
    "Size",
    "Defect Category",
    "Investigation Days",
]

OPERATOR_OPTIONS = [
    ("eq", "Equals (=)"),
    ("neq", "Not Equals (!=)"),
    ("gte", "Greater or Equal (>=)"),
    ("gt", "Greater Than (>)"),
    ("lte", "Less or Equal (<=)"),
    ("lt", "Less Than (<)"),
    ("contains", "Contains Text"),
    ("in", "In Comma-Separated List"),
    ("is_empty", "Is Blank / Empty"),
    ("not_empty", "Is Populated"),
]


def _get_admin_or_redirect(request: Request):
    try:
        user = get_current_user(request)
        if not user or (user.role or "").lower() != "admin":
            return None, RedirectResponse("/dashboard", status_code=302)
        return user, None
    except Exception:
        return None, RedirectResponse("/login", status_code=302)


def _require_admin_api(request: Request):
    try:
        user = get_current_user(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user or (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


# =====================================================================
# ADMIN UI: ALERT CENTER (OVERVIEW, RULES, RECIPIENTS, TEMPLATES, HISTORY, HEALTH)
# =====================================================================

@router.get("/admin/alerts", response_class=HTMLResponse)
def admin_alerts_center(
    request: Request,
    tab: str = Query("overview"),
    search: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    rule_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    msg: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    user, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    bootstrap.ensure_alert_system_initialized(db)
    cfg = service.get_or_create_config(db)

    all_rules = db.query(models.AlertRule).order_by(models.AlertRule.priority.asc(), models.AlertRule.id.desc()).all()
    groups = db.query(models.RecipientGroup).order_by(models.RecipientGroup.name.asc()).all()
    email_templates = db.query(models.EmailTemplate).order_by(models.EmailTemplate.id.asc()).all()

    # Build human-readable summaries and recipient group badges for each rule
    rules_view = []
    for r in all_rules:
        if search and search.lower() not in (r.name.lower() + " " + (r.description or "").lower()):
            continue
        to_names = [a.group.name for a in r.recipient_assignments if a.recipient_type == "TO" and a.group]
        cc_names = [a.group.name for a in r.recipient_assignments if a.recipient_type == "CC" and a.group]
        direct_emails = [a.email_address for a in r.recipient_assignments if a.email_address]
        rules_view.append({
            "rule": r,
            "human_summary": evaluator.build_human_readable_summary(r, to_names + direct_emails, cc_names),
            "to_groups": to_names + direct_emails,
            "cc_groups": cc_names,
        })

    # Delivery history query with filters
    deliv_query = db.query(models.AlertDelivery).join(models.AlertEvent)
    if severity:
        deliv_query = deliv_query.filter(models.AlertEvent.severity == severity.upper())
    if status:
        deliv_query = deliv_query.filter(models.AlertDelivery.status == status.upper())
    if rule_id:
        deliv_query = deliv_query.filter(models.AlertEvent.rule_id == rule_id)
    if event_type:
        deliv_query = deliv_query.filter(models.AlertEvent.event_type == event_type.upper())

    deliveries = deliv_query.order_by(models.AlertDelivery.id.desc()).limit(100).all()

    # Overview KPI metrics
    today_start = datetime.combine(date.today(), datetime.min.time())
    enabled_rules_count = sum(1 for r in all_rules if r.is_enabled)
    alerts_today = (
        db.query(models.AlertEvent)
        .filter(models.AlertEvent.triggered_at >= today_start, models.AlertEvent.event_type == "PRODUCTION")
        .count()
    )
    delivered_count = db.query(models.AlertDelivery).filter(models.AlertDelivery.status == "DELIVERED").count()
    failed_count = db.query(models.AlertDelivery).filter(models.AlertDelivery.status == "FAILED").count()
    queued_count = db.query(models.AlertDelivery).filter(models.AlertDelivery.status.in_(["QUEUED", "SENDING"])).count()
    critical_count = (
        db.query(models.AlertEvent)
        .filter(models.AlertEvent.severity == "CRITICAL", models.AlertEvent.event_type == "PRODUCTION")
        .count()
    )
    snapshot_count = db.query(models.DataRecordSnapshot).count()

    return templates.TemplateResponse(
        "alerts_center.html",
        {
            "request": request,
            "show_header": True,
            "user": user,
            "active_tab": tab,
            "flash_msg": msg,
            "config": cfg,
            "kpis": {
                "enabled_rules": enabled_rules_count,
                "total_rules": len(all_rules),
                "alerts_today": alerts_today,
                "delivered_count": delivered_count,
                "failed_count": failed_count,
                "queued_count": queued_count,
                "critical_count": critical_count,
                "snapshot_count": snapshot_count,
            },
            "rules_view": rules_view,
            "all_rules": all_rules,
            "recipient_groups": groups,
            "email_templates": email_templates,
            "deliveries": deliveries,
            "filters": {
                "search": search or "",
                "severity": severity or "",
                "status": status or "",
                "rule_id": rule_id or "",
                "event_type": event_type or "",
            },
            "field_labels": tmpl_engine.FIELD_DISPLAY_LABELS,
        },
    )


# =====================================================================
# ADMIN UI: MULTI-STEP / SECTIONED RULE BUILDER
# =====================================================================

@router.get("/admin/alerts/builder", response_class=HTMLResponse)
def admin_alerts_builder(
    request: Request,
    id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    user, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    bootstrap.ensure_alert_system_initialized(db)
    rule = db.query(models.AlertRule).filter(models.AlertRule.id == id).first() if id else None
    groups = db.query(models.RecipientGroup).filter(models.RecipientGroup.is_active == True).all()
    email_templates = db.query(models.EmailTemplate).all()

    selected_to_groups = []
    selected_cc_groups = []
    extra_to_emails = []
    extra_cc_emails = []

    if rule:
        for a in rule.recipient_assignments:
            if a.group_id:
                if a.recipient_type == "CC":
                    selected_cc_groups.append(a.group_id)
                else:
                    selected_to_groups.append(a.group_id)
            elif a.email_address:
                if a.recipient_type == "CC":
                    extra_cc_emails.append(a.email_address)
                else:
                    extra_to_emails.append(a.email_address)

    return templates.TemplateResponse(
        "alerts_builder.html",
        {
            "request": request,
            "show_header": True,
            "user": user,
            "rule": rule,
            "recipient_groups": groups,
            "email_templates": email_templates,
            "trigger_options": TRIGGER_TYPE_OPTIONS,
            "field_options": DATA_FIELD_OPTIONS,
            "operator_options": OPERATOR_OPTIONS,
            "selected_to_groups": selected_to_groups,
            "selected_cc_groups": selected_cc_groups,
            "extra_to_emails": ", ".join(extra_to_emails),
            "extra_cc_emails": ", ".join(extra_cc_emails),
        },
    )


@router.post("/admin/alerts/rules/save")
async def save_alert_rule(
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    form = await request.form()
    rule_id_raw = str(form.get("rule_id", "")).strip()
    rule_id = int(rule_id_raw) if rule_id_raw.isdigit() else None

    if rule_id:
        rule = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
    else:
        rule = models.AlertRule(created_by=user.username)
        db.add(rule)

    rule.name = str(form.get("name", "Untitled Rule")).strip()
    rule.description = str(form.get("description", "")).strip()
    rule.is_enabled = form.get("is_enabled") in ("on", "true", "1", "yes")
    rule.priority = int(form.get("priority") or 5)
    rule.rule_category = str(form.get("rule_category", "EVENT")).upper()
    rule.trigger_type = str(form.get("trigger_type", "NOK_DETECTED")).strip()
    rule.data_source = str(form.get("data_source", "ALL")).strip()
    rule.severity = str(form.get("severity", "CRITICAL")).upper()
    rule.logical_operator = str(form.get("logical_operator", "AND")).upper()

    tw_raw = str(form.get("time_window_hours", "")).strip()
    rule.time_window_hours = float(tw_raw) if tw_raw else None

    th_raw = str(form.get("threshold_value", "")).strip()
    rule.threshold_value = float(th_raw) if th_raw else None

    rule.group_by_field = str(form.get("group_by_field", "")).strip() or None
    rule.cooldown_minutes = int(form.get("cooldown_minutes") or 60)
    rule.start_date = str(form.get("start_date", "")).strip() or None
    rule.end_date = str(form.get("end_date", "")).strip() or None
    rule.schedule_time = str(form.get("schedule_time", "")).strip() or None
    rule.schedule_days = str(form.get("schedule_days", "Mon,Tue,Wed,Thu,Fri,Sat")).strip()

    tmpl_id_raw = str(form.get("template_id", "")).strip()
    rule.template_id = int(tmpl_id_raw) if tmpl_id_raw.isdigit() else None
    rule.custom_subject = str(form.get("custom_subject", "")).strip()
    rule.custom_body = str(form.get("custom_body", "")).strip()
    rule.include_report_attachment = form.get("include_report_attachment") in ("on", "true", "1")
    rule.webhook_url_override = str(form.get("webhook_url_override", "")).strip()
    rule.max_retries = int(form.get("max_retries") or 3)
    rule.retry_backoff_seconds = int(form.get("retry_backoff_seconds") or 60)

    db.flush()

    # Replace conditions
    db.query(models.AlertCondition).filter(models.AlertCondition.rule_id == rule.id).delete()
    fields = form.getlist("cond_field")
    ops = form.getlist("cond_operator")
    vals = form.getlist("cond_value")
    for f_name, op_val, v_val in zip(fields, ops, vals):
        f_clean = str(f_name).strip()
        if not f_clean:
            continue
        db.add(
            models.AlertCondition(
                rule_id=rule.id,
                condition_group=1,
                field_name=f_clean,
                operator=str(op_val or "eq").strip(),
                value=str(v_val or "").strip(),
            )
        )

    # Replace recipient assignments
    db.query(models.RuleRecipientAssignment).filter(models.RuleRecipientAssignment.rule_id == rule.id).delete()
    for gid in form.getlist("to_group_ids"):
        if str(gid).isdigit():
            db.add(models.RuleRecipientAssignment(rule_id=rule.id, recipient_type="TO", group_id=int(gid)))
    for gid in form.getlist("cc_group_ids"):
        if str(gid).isdigit():
            db.add(models.RuleRecipientAssignment(rule_id=rule.id, recipient_type="CC", group_id=int(gid)))

    extra_to = str(form.get("extra_to_emails", "")).strip()
    if extra_to:
        db.add(models.RuleRecipientAssignment(rule_id=rule.id, recipient_type="TO", email_address=extra_to))

    extra_cc = str(form.get("extra_cc_emails", "")).strip()
    if extra_cc:
        db.add(models.RuleRecipientAssignment(rule_id=rule.id, recipient_type="CC", email_address=extra_cc))

    db.commit()
    return RedirectResponse("/admin/alerts?tab=rules&msg=Rule+saved+successfully", status_code=302)


@router.post("/admin/alerts/rules/{rule_id}/toggle")
def toggle_alert_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    rule = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
    if rule:
        rule.is_enabled = not rule.is_enabled
        db.commit()
    return RedirectResponse("/admin/alerts?tab=rules&msg=Rule+status+updated", status_code=302)


@router.post("/admin/alerts/rules/{rule_id}/duplicate")
def duplicate_alert_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    orig = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
    if not orig:
        return RedirectResponse("/admin/alerts?tab=rules", status_code=302)

    copy_rule = models.AlertRule(
        name=f"{orig.name} (Copy)",
        description=orig.description,
        is_enabled=False,
        priority=orig.priority,
        rule_category=orig.rule_category,
        trigger_type=orig.trigger_type,
        data_source=orig.data_source,
        severity=orig.severity,
        logical_operator=orig.logical_operator,
        time_window_hours=orig.time_window_hours,
        threshold_value=orig.threshold_value,
        group_by_field=orig.group_by_field,
        cooldown_minutes=orig.cooldown_minutes,
        schedule_time=orig.schedule_time,
        schedule_days=orig.schedule_days,
        template_id=orig.template_id,
        custom_subject=orig.custom_subject,
        custom_body=orig.custom_body,
        max_retries=orig.max_retries,
        retry_backoff_seconds=orig.retry_backoff_seconds,
        created_by=user.username,
    )
    db.add(copy_rule)
    db.flush()

    for c in orig.conditions:
        db.add(
            models.AlertCondition(
                rule_id=copy_rule.id,
                condition_group=c.condition_group,
                field_name=c.field_name,
                operator=c.operator,
                value=c.value,
            )
        )
    for a in orig.recipient_assignments:
        db.add(
            models.RuleRecipientAssignment(
                rule_id=copy_rule.id,
                recipient_type=a.recipient_type,
                group_id=a.group_id,
                email_address=a.email_address,
                dynamic_field=a.dynamic_field,
            )
        )
    db.commit()
    return RedirectResponse("/admin/alerts?tab=rules&msg=Rule+duplicated", status_code=302)


@router.post("/admin/alerts/rules/{rule_id}/delete")
def delete_alert_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    rule = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse("/admin/alerts?tab=rules&msg=Rule+deleted", status_code=302)


# =====================================================================
# RECIPIENT GROUP & RECIPIENT MANAGEMENT
# =====================================================================

@router.post("/admin/alerts/recipients/group/save")
def save_recipient_group(
    request: Request,
    group_id: Optional[str] = Form(None),
    name: str = Form(...),
    department_code: str = Form(""),
    description: str = Form(""),
    emails_text: str = Form(""),
    db: Session = Depends(get_db),
):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    gid = int(group_id) if group_id and str(group_id).isdigit() else None
    if gid:
        grp = db.query(models.RecipientGroup).filter(models.RecipientGroup.id == gid).first()
    else:
        grp = models.RecipientGroup()
        db.add(grp)

    grp.name = name.strip()
    grp.department_code = department_code.strip()
    grp.description = description.strip()
    grp.is_active = True
    db.flush()

    if emails_text.strip():
        db.query(models.GroupMembership).filter(models.GroupMembership.group_id == grp.id).delete()
        raw_tokens = emails_text.replace(";", ",").replace("\n", ",").split(",")
        seen_ids = set()
        for token in raw_tokens:
            clean_e = token.strip()
            if not clean_e or "@" not in clean_e:
                continue
            rec = db.query(models.Recipient).filter(models.Recipient.email == clean_e).first()
            if not rec:
                disp = clean_e.split("@")[0].replace(".", " ").title()
                rec = models.Recipient(email=clean_e, display_name=disp, department=grp.department_code, is_active=True)
                db.add(rec)
                db.flush()
            if rec.id not in seen_ids:
                seen_ids.add(rec.id)
                db.add(models.GroupMembership(group_id=grp.id, recipient_id=rec.id))

    db.commit()
    return RedirectResponse("/admin/alerts?tab=recipients&msg=Recipient+group+saved", status_code=302)


@router.post("/admin/alerts/recipients/group/{group_id}/toggle")
def toggle_recipient_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect
    grp = db.query(models.RecipientGroup).filter(models.RecipientGroup.id == group_id).first()
    if grp:
        grp.is_active = not grp.is_active
        db.commit()
    return RedirectResponse("/admin/alerts?tab=recipients&msg=Group+status+updated", status_code=302)


@router.post("/admin/alerts/recipients/group/{group_id}/delete")
def delete_recipient_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect
    grp = db.query(models.RecipientGroup).filter(models.RecipientGroup.id == group_id).first()
    if grp:
        db.delete(grp)
        db.commit()
    return RedirectResponse("/admin/alerts?tab=recipients&msg=Group+deleted", status_code=302)


# =====================================================================
# EMAIL TEMPLATE MANAGEMENT
# =====================================================================

@router.post("/admin/alerts/templates/save")
async def save_email_template(request: Request, db: Session = Depends(get_db)):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    form = await request.form()
    tid_raw = str(form.get("template_id", "")).strip()
    tid = int(tid_raw) if tid_raw.isdigit() else None

    if tid:
        tmpl = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == tid).first()
    else:
        tmpl = models.EmailTemplate()
        db.add(tmpl)

    tmpl.name = str(form.get("name", "Custom MIS Template")).strip()
    tmpl.description = str(form.get("description", "")).strip()
    tmpl.subject_template = str(form.get("subject_template", "")).strip()
    tmpl.intro_text = str(form.get("intro_text", "Dear Team,")).strip()
    tmpl.observation_template = str(form.get("observation_template", "")).strip()
    tmpl.action_template = str(form.get("action_template", "")).strip()
    tmpl.footer_text = str(form.get("footer_text", "")).strip()

    selected_fields = form.getlist("table_fields")
    if selected_fields:
        tmpl.table_fields_json = json.dumps([str(f) for f in selected_fields])

    db.commit()
    return RedirectResponse("/admin/alerts?tab=templates&msg=Email+template+saved", status_code=302)


# =====================================================================
# SYSTEM HEALTH & CONFIGURATION
# =====================================================================

@router.post("/admin/alerts/config/save")
def save_alert_config(
    request: Request,
    power_automate_webhook_url: str = Form(""),
    secret_header_name: str = Form("X-WSA-Secret-Token"),
    secret_header_value: str = Form(""),
    dashboard_base_url: str = Form("http://localhost:8080"),
    poll_interval_seconds: int = Form(60),
    alerts_paused: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    _, redirect = _get_admin_or_redirect(request)
    if redirect:
        return redirect

    cfg = service.get_or_create_config(db)
    cfg.power_automate_webhook_url = power_automate_webhook_url.strip()
    cfg.secret_header_name = secret_header_name.strip() or "X-WSA-Secret-Token"
    if secret_header_value.strip() and secret_header_value.strip() != "********":
        cfg.secret_header_value = secret_header_value.strip()
    cfg.dashboard_base_url = dashboard_base_url.strip() or "http://localhost:8080"
    cfg.poll_interval_seconds = max(15, int(poll_interval_seconds or 60))
    cfg.alerts_paused = alerts_paused in ("on", "true", "1")
    db.commit()
    return RedirectResponse("/admin/alerts?tab=health&msg=System+configuration+updated", status_code=302)


# =====================================================================
# JSON / REST APIs FOR TEST ALERT, MANUAL RETRY, EVALUATION & POWER AUTOMATE
# =====================================================================

@router.post("/api/alerts/rules/{rule_id}/test")
def api_test_alert_rule(
    rule_id: int,
    request: Request,
    send_webhook: bool = Query(False),
    db: Session = Depends(get_db),
):
    _require_admin_api(request)
    rule = db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    result = service.run_rule_test_preview(db, rule, record_test_event=send_webhook)
    return JSONResponse(result)


@router.post("/api/alerts/preview-draft")
async def api_preview_draft_rule(request: Request, db: Session = Depends(get_db)):
    """Renders a live preview of an unsaved rule directly from the Rule Builder form."""
    _require_admin_api(request)
    body = await request.json()

    temp_rule = models.AlertRule(
        id=0,
        name=body.get("name") or "Draft Rule Preview",
        rule_category=body.get("rule_category") or "EVENT",
        trigger_type=body.get("trigger_type") or "NOK_DETECTED",
        data_source=body.get("data_source") or "ALL",
        severity=body.get("severity") or "CRITICAL",
        logical_operator=body.get("logical_operator") or "AND",
        time_window_hours=float(body["time_window_hours"]) if body.get("time_window_hours") else None,
        threshold_value=float(body["threshold_value"]) if body.get("threshold_value") else None,
        group_by_field=body.get("group_by_field") or None,
        custom_subject=body.get("custom_subject") or "",
        custom_body=body.get("custom_body") or "",
    )
    temp_rule.conditions = [
        models.AlertCondition(
            condition_group=1,
            field_name=c.get("field_name", "Status"),
            operator=c.get("operator", "eq"),
            value=c.get("value", "NOK"),
        )
        for c in body.get("conditions", [])
        if c.get("field_name")
    ]
    if body.get("template_id") and str(body["template_id"]).isdigit():
        temp_rule.template = db.query(models.EmailTemplate).filter(models.EmailTemplate.id == int(body["template_id"])).first()

    preview = service.run_rule_test_preview(db, temp_rule, record_test_event=False)
    return JSONResponse(preview)


@router.post("/api/alerts/delivery/{delivery_id}/retry")
def api_retry_delivery(delivery_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin_api(request)
    deliv = db.query(models.AlertDelivery).filter(models.AlertDelivery.id == delivery_id).first()
    if not deliv:
        raise HTTPException(status_code=404, detail="Delivery record not found")

    rule = deliv.event.rule if deliv.event else None
    ok = power_automate.attempt_delivery(db, deliv, rule)
    return {
        "status": deliv.status,
        "success": ok,
        "retry_count": deliv.retry_count,
        "error_message": deliv.error_message,
    }


@router.post("/api/alerts/evaluate")
def api_evaluate_alerts(
    force_all: bool = Query(False),
    include_scheduled: bool = Query(False),
    db: Session = Depends(get_db),
):
    bootstrap.ensure_alert_system_initialized(db)
    return service.run_evaluation_cycle(
        db,
        force_evaluate_all=force_all,
        include_scheduled=include_scheduled,
    )


@router.post("/api/alerts/poll")
def api_poll_pending_alerts(db: Session = Depends(get_db)):
    """
    Power Automate Poll Endpoint:
    Returns all QUEUED deliveries in structured Power Automate JSON format.
    """
    bootstrap.ensure_alert_system_initialized(db)
    queued = (
        db.query(models.AlertDelivery)
        .filter(models.AlertDelivery.status == "QUEUED")
        .order_by(models.AlertDelivery.id.asc())
        .limit(50)
        .all()
    )
    results = []
    for d in queued:
        try:
            payload = json.loads(d.payload_json or "{}")
        except Exception:
            payload = {}
        if payload:
            results.append(payload)
    return results


@router.post("/api/alerts/delivery/{delivery_id}/ack")
@router.post("/api/alerts/mark-sent/{delivery_id}")
def api_acknowledge_delivery(
    delivery_id: int,
    ack: Optional[schemas.DeliveryAckInput] = None,
    db: Session = Depends(get_db),
):
    """Callback for Power Automate to mark a polled delivery as DELIVERED or FAILED."""
    deliv = db.query(models.AlertDelivery).filter(models.AlertDelivery.id == delivery_id).first()
    if not deliv:
        # Fallback lookup by event_id for backwards compatibility
        deliv = db.query(models.AlertDelivery).filter(models.AlertDelivery.event_id == delivery_id).first()
    if not deliv:
        raise HTTPException(status_code=404, detail="Delivery not found")

    now = datetime.utcnow()
    status_val = (ack.status if ack else "DELIVERED").upper()
    deliv.last_attempt_at = now
    deliv.http_status_code = ack.http_status_code if ack else 200

    if status_val in ("DELIVERED", "SENT", "SUCCESS"):
        deliv.status = "DELIVERED"
        deliv.delivered_at = now
        deliv.error_message = ""
        cfg = service.get_or_create_config(db)
        cfg.last_webhook_success_at = now
    else:
        deliv.status = "FAILED"
        deliv.error_message = (ack.error_message if ack else "Reported failed by Power Automate")

    db.commit()
    return {"status": "acknowledged", "delivery_id": deliv.id, "delivery_status": deliv.status}
