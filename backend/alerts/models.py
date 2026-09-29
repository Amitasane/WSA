from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    severity = Column(String, default="Info") # Info, Warning, High, Critical
    trigger_type = Column(String) # NOK, Threshold, MissingData, etc.
    logical_operator = Column(String, default="AND") # AND / OR
    time_window_mins = Column(Integer, nullable=True)
    group_by = Column(String, nullable=True)
    threshold = Column(Float, nullable=True)
    cooldown_mins = Column(Integer, default=60)
    priority = Column(Integer, default=0)
    email_template = Column(Text, nullable=True)
    
    conditions = relationship("AlertCondition", back_populates="rule", cascade="all, delete-orphan")
    events = relationship("AlertEvent", back_populates="rule")

class AlertCondition(Base):
    __tablename__ = "alert_conditions"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"))
    field_name = Column(String) # Station, Shift, Customer, Total particle found, etc.
    operator = Column(String) # equals, not_equals, > , <, >=, <=, contains
    value = Column(String)
    
    rule = relationship("AlertRule", back_populates="conditions")

class AlertRecipientGroup(Base):
    __tablename__ = "alert_recipient_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    emails = Column(Text) # comma-separated
    description = Column(Text, nullable=True)

class AlertEvent(Base):
    __tablename__ = "alert_events"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"))
    severity = Column(String)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    
    # context
    station = Column(String, nullable=True)
    customer = Column(String, nullable=True)
    shift = Column(String, nullable=True)
    message = Column(Text)
    records_json = Column(Text) # JSON dump of triggering records context
    
    # lifecycle
    notification_status = Column(String, default="PENDING") # PENDING, SENT, FAILED
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    rule = relationship("AlertRule", back_populates="events")
