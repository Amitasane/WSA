from backend.alerts.engine import evaluate_rule_on_records
from backend.alerts.models import AlertRule, AlertCondition

def test_nok_detection_and_condition():
    # Setup mock data
    mock_records = [
        {"status": "NOK", "Station": "QMM3", "Shift": "1st", "Customer": "Bosch"},
        {"status": "OK", "Station": "QMM3", "Shift": "1st", "Customer": "Bosch"},
        {"status": "NOK", "Station": "QMM2", "Shift": "2nd", "Customer": "Tata"},
    ]
    
    # Test simple NOK trigger
    rule_nok = AlertRule(name="All NOKs", trigger_type="NOK", logical_operator="AND", conditions=[])
    triggered = evaluate_rule_on_records(rule_nok, mock_records, None)
    assert len(triggered) == 2
    
    # Test NOK + Condition (Station == QMM3)
    cond1 = AlertCondition(field_name="Station", operator="equals", value="QMM3")
    rule_qmm3 = AlertRule(name="QMM3 NOKs", trigger_type="NOK", logical_operator="AND", conditions=[cond1])
    triggered2 = evaluate_rule_on_records(rule_qmm3, mock_records, None)
    assert len(triggered2) == 1
    assert triggered2[0]["Station"] == "QMM3"

def test_numeric_thresholds():
    mock_records = [
        {"status": "NOK", "_total_particle": 5},
        {"status": "NOK", "_total_particle": 2},
    ]
    
    # Test numeric greater than
    cond = AlertCondition(field_name="_total_particle", operator=">=", value="3")
    rule = AlertRule(name="High Particles", trigger_type="NOK", logical_operator="AND", conditions=[cond])
    triggered = evaluate_rule_on_records(rule, mock_records, None)
    
    assert len(triggered) == 1
    assert triggered[0]["_total_particle"] == 5

def test_or_conditions():
    mock_records = [
        {"status": "NOK", "Customer": "Tata"},
        {"status": "NOK", "Customer": "Mahindra"},
        {"status": "NOK", "Customer": "Bosch"},
    ]
    
    cond1 = AlertCondition(field_name="Customer", operator="equals", value="Tata")
    cond2 = AlertCondition(field_name="Customer", operator="equals", value="Mahindra")
    
    rule = AlertRule(name="Tata OR Mahindra", trigger_type="NOK", logical_operator="OR", conditions=[cond1, cond2])
    triggered = evaluate_rule_on_records(rule, mock_records, None)
    
    assert len(triggered) == 2
    
# Run pytest in terminal to execute
