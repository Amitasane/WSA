from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class AlertConditionBase(BaseModel):
    field_name: str
    operator: str
    value: str

class AlertConditionCreate(AlertConditionBase):
    pass

class AlertConditionSchema(AlertConditionBase):
    id: int
    rule_id: int

    class Config:
        from_attributes = True

class AlertRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_enabled: bool = True
    severity: str = "Info"
    trigger_type: str = "NOK"
    logical_operator: str = "AND"
    time_window_mins: Optional[int] = None
    group_by: Optional[str] = None
    threshold: Optional[float] = None
    cooldown_mins: int = 60
    priority: int = 0
    email_template: Optional[str] = None

class AlertRuleCreate(AlertRuleBase):
    conditions: List[AlertConditionCreate] = []

class AlertRuleSchema(AlertRuleBase):
    id: int
    conditions: List[AlertConditionSchema] = []

    class Config:
        from_attributes = True

class AlertEventSchema(BaseModel):
    id: int
    rule_id: int
    severity: str
    triggered_at: datetime
    station: Optional[str]
    customer: Optional[str]
    shift: Optional[str]
    message: str
    notification_status: str

    class Config:
        from_attributes = True

class PowerAutomatePollResponse(BaseModel):
    alert_id: int
    rule_id: int
    rule_name: str
    severity: str
    trigger_type: str
    triggered_at: str
    station: Optional[str]
    customer: Optional[str]
    shift: Optional[str]
    records: List[Any]
    message: str
    wsa_url: str
