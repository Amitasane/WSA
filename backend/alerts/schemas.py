from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConditionInput(BaseModel):
    condition_group: int = 1
    field_name: str
    operator: str = "eq"
    value: str = ""


class RecipientAssignmentInput(BaseModel):
    recipient_type: str = "TO"  # TO, CC, BCC
    group_id: Optional[int] = None
    email_address: Optional[str] = None
    dynamic_field: Optional[str] = None


class RuleCreateUpdateSchema(BaseModel):
    name: str
    description: str = ""
    is_enabled: bool = True
    priority: int = 5
    rule_category: str = "EVENT"  # EVENT or SCHEDULED
    trigger_type: str = "NOK_DETECTED"
    data_source: str = "ALL"
    severity: str = "CRITICAL"
    logical_operator: str = "AND"
    time_window_hours: Optional[float] = None
    threshold_value: Optional[float] = None
    group_by_field: Optional[str] = None
    cooldown_minutes: int = 60
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    schedule_time: Optional[str] = None
    schedule_days: str = "Mon,Tue,Wed,Thu,Fri,Sat"
    template_id: Optional[int] = None
    custom_subject: str = ""
    custom_body: str = ""
    include_report_attachment: bool = False
    webhook_url_override: str = ""
    max_retries: int = 3
    retry_backoff_seconds: int = 60
    conditions: List[ConditionInput] = Field(default_factory=list)
    recipients: List[RecipientAssignmentInput] = Field(default_factory=list)


class RecipientGroupInput(BaseModel):
    name: str
    description: str = ""
    department_code: str = ""
    is_active: bool = True
    emails: List[str] = Field(default_factory=list)


class EmailTemplateInput(BaseModel):
    name: str
    description: str = ""
    subject_template: str
    intro_text: str = "Dear Team,"
    body_template: str = ""
    observation_template: str = ""
    action_template: str = ""
    footer_text: str = ""
    table_fields: List[str] = Field(default_factory=list)
    is_default: bool = False


class DeliveryAckInput(BaseModel):
    status: str = "DELIVERED"  # DELIVERED or FAILED
    error_message: str = ""
    http_status_code: int = 200


class PowerAutomatePayload(BaseModel):
    event_id: str
    delivery_id: int
    is_test: bool = False
    rule_id: Optional[int] = None
    rule_name: str
    rule_category: str = "EVENT"
    trigger_type: str
    severity: str
    triggered_at: str
    date: str = ""
    shift: str = ""
    station: str = ""
    auditor: str = ""
    customer: str = ""
    injector_type: str = ""
    parts_checked: float = 0
    nok_count: int = 0
    nok_rate: float = 0.0
    total_particles: float = 0
    particle_location: str = ""
    chemistry: str = ""
    size: str = ""
    rejection_date: str = ""
    rejection_shift: str = ""
    observation: str = ""
    required_action: str = ""
    dashboard_url: str = ""
    recipients: List[str] = Field(default_factory=list)
    cc_recipients: List[str] = Field(default_factory=list)
    bcc_recipients: List[str] = Field(default_factory=list)
    email_subject: str = ""
    email_body_html: str = ""
    matched_records: List[Dict[str, Any]] = Field(default_factory=list)
