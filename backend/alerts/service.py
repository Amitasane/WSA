from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import models, engine, schemas

def check_cooldown(db: Session, rule: models.AlertRule) -> bool:
    """Check if the rule is on cooldown and should not fire yet."""
    last_event = db.query(models.AlertEvent).filter(
        models.AlertEvent.rule_id == rule.id
    ).order_by(models.AlertEvent.triggered_at.desc()).first()
    
    if last_event and rule.cooldown_mins:
        time_since_last = datetime.utcnow() - last_event.triggered_at
        if time_since_last < timedelta(minutes=rule.cooldown_mins):
            return True # Still on cooldown
    return False

def evaluate_and_trigger(db: Session, records: List[Dict[str, Any]]) -> List[models.AlertEvent]:
    """Evaluates all active rules against the current dataset and generates events."""
    active_rules = db.query(models.AlertRule).filter(models.AlertRule.is_enabled == True).all()
    new_events = []
    
    for rule in active_rules:
        if check_cooldown(db, rule):
            continue
            
        triggered_records = engine.evaluate_rule_on_records(rule, records, db)
        
        if not triggered_records:
            continue
            
        # Grouping or generic suppression logic can be expanded here
        # For now, we create one grouped event containing all triggering records
        
        event = models.AlertEvent(
            rule_id=rule.id,
            severity=rule.severity,
            message=f"Rule '{rule.name}' triggered on {len(triggered_records)} records.",
            records_json=str([r.get("id", r.get("customer_complaint_no", "unknown")) for r in triggered_records]),
            notification_status="PENDING",
            station=triggered_records[0].get("Station") if triggered_records else None,
            customer=triggered_records[0].get("Customer") if triggered_records else None,
            shift=triggered_records[0].get("Shift") if triggered_records else None,
        )
        db.add(event)
        new_events.append(event)
        
    db.commit()
    for e in new_events:
        db.refresh(e)
    return new_events

def get_pending_alerts_for_power_automate(db: Session) -> List[schemas.PowerAutomatePollResponse]:
    """Fetch pending events for Power Automate and return formatted schema."""
    pending_events = db.query(models.AlertEvent).filter(
        models.AlertEvent.notification_status == "PENDING"
    ).all()
    
    response = []
    for event in pending_events:
        rule = event.rule
        response.append(schemas.PowerAutomatePollResponse(
            alert_id=event.id,
            rule_id=rule.id,
            rule_name=rule.name,
            severity=event.severity,
            trigger_type=rule.trigger_type,
            triggered_at=event.triggered_at.isoformat(),
            station=event.station,
            customer=event.customer,
            shift=event.shift,
            records=[], # Would load actual full records here if needed
            message=event.message,
            wsa_url=f"http://localhost:8000/alerts/history/{event.id}"
        ))
    return response

def mark_alert_as_sent(db: Session, alert_id: int):
    event = db.query(models.AlertEvent).filter(models.AlertEvent.id == alert_id).first()
    if event:
        event.notification_status = "SENT"
        db.commit()
