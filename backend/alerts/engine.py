import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

def evaluate_condition(record: Dict[str, Any], field_name: str, operator: str, value: str) -> bool:
    rec_val = record.get(field_name)
    if rec_val is None:
        return False
    
    # Try numeric comparison if possible
    try:
        rec_num = float(rec_val)
        val_num = float(value)
        is_num = True
    except (ValueError, TypeError):
        is_num = False
        rec_val = str(rec_val).strip().lower()
        value = str(value).strip().lower()
        
    if operator == "equals":
        return rec_num == val_num if is_num else rec_val == value
    elif operator == "not_equals":
        return rec_num != val_num if is_num else rec_val != value
    elif operator == ">":
        return is_num and rec_num > val_num
    elif operator == "<":
        return is_num and rec_num < val_num
    elif operator == ">=":
        return is_num and rec_num >= val_num
    elif operator == "<=":
        return is_num and rec_num <= val_num
    elif operator == "contains":
        return not is_num and value in rec_val
    return False

def evaluate_rule_on_records(rule, records: List[Dict[str, Any]], db) -> List[Dict[str, Any]]:
    # This is a simplified engine evaluating a single rule over a list of records
    # For a real implementation, time_window, grouping, cooldown logic goes here.
    
    triggered_records = []
    
    for rec in records:
        # Base filter by trigger type
        if rule.trigger_type == "NOK" and rec.get("status") != "NOK":
            continue
            
        if not rule.conditions:
            triggered_records.append(rec)
            continue
            
        # Evaluate conditions
        condition_results = [
            evaluate_condition(rec, cond.field_name, cond.operator, cond.value)
            for cond in rule.conditions
        ]
        
        if rule.logical_operator == "AND" and all(condition_results):
            triggered_records.append(rec)
        elif rule.logical_operator == "OR" and any(condition_results):
            triggered_records.append(rec)
            
    return triggered_records
