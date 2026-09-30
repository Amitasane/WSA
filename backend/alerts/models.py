from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from backend.database import Base


class AlertConfiguration(Base):
    __tablename__ = "alert_configurations"

    id = Column(Integer, primary_key=True, index=True)
    power_automate_webhook_url = Column(String, default="")
    secret_header_name = Column(String, default="X-WSA-Secret-Token")
    secret_header_value = Column(String, default="")
    dashboard_base_url = Column(String, default="http://localhost:8080")
    poll_interval_seconds = Column(Integer, default=60)
    alerts_paused = Column(Boolean, default=False)
    default_sender_name = Column(String, default="WSA Quality Alert System (PS/QMM2-NaP)")
    last_webhook_success_at = Column(DateTime, nullable=True)
    last_webhook_error = Column(Text, default="")
    last_evaluation_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecipientGroup(Base):
    __tablename__ = "alert_recipient_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, default="")
    department_code = Column(String, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    rule_assignments = relationship(
        "RuleRecipientAssignment",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Recipient(Base):
    __tablename__ = "alert_recipients"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    display_name = Column(String, default="")
    department = Column(String, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship(
        "GroupMembership",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )


class GroupMembership(Base):
    __tablename__ = "alert_group_memberships"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("alert_recipient_groups.id", ondelete="CASCADE"))
    recipient_id = Column(Integer, ForeignKey("alert_recipients.id", ondelete="CASCADE"))

    group = relationship("RecipientGroup", back_populates="memberships")
    recipient = relationship("Recipient", back_populates="memberships")


class EmailTemplate(Base):
    __tablename__ = "alert_email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, default="")
    subject_template = Column(Text, default="[{{severity}}] CRIN - Line 5 internal rejection analysis MIS - {{rule_name}}")
    intro_text = Column(Text, default="Dear Team,")
    body_template = Column(Text, default="")
    observation_template = Column(Text, default="")
    action_template = Column(Text, default="")
    footer_text = Column(
        Text,
        default="Best regards,\nQuality Management Methods, Nozzles (PS/QMM2-NaP)\nBosch Limited | Bengaluru-560030 | INDIA",
    )
    severity_wording_json = Column(
        Text,
        default='{"INFO": "Information Update", "WARNING": "Quality Warning - Attention Required", "CRITICAL": "Critical Quality Alert - Immediate Action Required"}',
    )
    table_fields_json = Column(
        Text,
        default='["date", "shift", "station", "customer", "injector_type", "parts_checked", "nok_count", "nok_rate", "particle_location", "rejection_date", "rejection_shift"]',
    )
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rules = relationship("AlertRule", back_populates="template")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, default="")
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=5)
    rule_category = Column(String, default="EVENT")  # EVENT or SCHEDULED
    trigger_type = Column(String, default="NOK_DETECTED")
    data_source = Column(String, default="ALL")  # PARTICLE_SUMMARY, INVESTIGATION, ALL
    severity = Column(String, default="CRITICAL")  # INFO, WARNING, CRITICAL
    logical_operator = Column(String, default="AND")  # AND / OR

    # Windowed & threshold configuration
    time_window_hours = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    group_by_field = Column(String, nullable=True)
    cooldown_minutes = Column(Integer, default=60)

    # Schedule & validity window
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    schedule_time = Column(String, nullable=True)  # e.g. "17:00" or "SHIFT_END"
    schedule_days = Column(String, default="Mon,Tue,Wed,Thu,Fri,Sat")

    # Template & custom overrides
    template_id = Column(Integer, ForeignKey("alert_email_templates.id"), nullable=True)
    custom_subject = Column(Text, default="")
    custom_body = Column(Text, default="")
    include_report_attachment = Column(Boolean, default=False)

    # Delivery & retry policy
    webhook_url_override = Column(String, default="")
    max_retries = Column(Integer, default=3)
    retry_backoff_seconds = Column(Integer, default=60)

    created_by = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = Column(DateTime, nullable=True)

    template = relationship("EmailTemplate", back_populates="rules")
    conditions = relationship(
        "AlertCondition",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AlertCondition.id",
    )
    recipient_assignments = relationship(
        "RuleRecipientAssignment",
        back_populates="rule",
        cascade="all, delete-orphan",
    )
    events = relationship(
        "AlertEvent",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class AlertCondition(Base):
    __tablename__ = "alert_conditions"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"))
    condition_group = Column(Integer, default=1)
    field_name = Column(String)
    operator = Column(String, default="eq")  # eq, neq, gt, gte, lt, lte, contains, not_contains, in, is_empty, not_empty
    value = Column(String, default="")

    rule = relationship("AlertRule", back_populates="conditions")


class RuleRecipientAssignment(Base):
    __tablename__ = "alert_rule_recipients"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"))
    recipient_type = Column(String, default="TO")  # TO, CC, BCC
    group_id = Column(Integer, ForeignKey("alert_recipient_groups.id", ondelete="CASCADE"), nullable=True)
    email_address = Column(String, nullable=True)  # For direct individual email
    dynamic_field = Column(String, nullable=True)  # e.g. "Auditor" or "Responsibility"

    rule = relationship("AlertRule", back_populates="recipient_assignments")
    group = relationship("RecipientGroup", back_populates="rule_assignments")


class DataRecordSnapshot(Base):
    __tablename__ = "alert_data_snapshots"

    record_key = Column(String, primary_key=True, index=True)
    data_source = Column(String, index=True)  # PARTICLE_SUMMARY or INVESTIGATION
    row_hash = Column(String, index=True)
    status = Column(String, default="")
    record_date_iso = Column(String, default="")
    station = Column(String, default="")
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    summary_json = Column(Text, default="{}")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    event_uuid = Column(String, unique=True, index=True)
    fingerprint = Column(String, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    rule_name_snapshot = Column(String, default="")
    trigger_type = Column(String, default="")
    severity = Column(String, default="CRITICAL")
    event_type = Column(String, default="PRODUCTION")  # PRODUCTION vs TEST
    station = Column(String, default="")
    customer = Column(String, default="")
    shift = Column(String, default="")
    trigger_reason = Column(Text, default="")
    context_json = Column(Text, default="{}")
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    rule = relationship("AlertRule", back_populates="events")
    deliveries = relationship(
        "AlertDelivery",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("alert_events.id", ondelete="CASCADE"))
    channel = Column(String, default="POWER_AUTOMATE")
    status = Column(String, default="QUEUED", index=True)  # QUEUED, SENDING, DELIVERED, FAILED, SUPPRESSED_COOLDOWN
    recipients_to_json = Column(Text, default="[]")
    recipients_cc_json = Column(Text, default="[]")
    recipients_bcc_json = Column(Text, default="[]")
    rendered_subject = Column(Text, default="")
    rendered_body_html = Column(Text, default="")
    payload_json = Column(Text, default="{}")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("AlertEvent", back_populates="deliveries")
