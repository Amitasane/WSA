from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from backend.alerts.models import AlertRule, AlertCondition

FIELD_ALIASES = {
    "Date": "date",
    "Shift": "shift",
    "Station": "station",
    "Auditor": "auditor",
    "Customer": "customer",
    "Type": "injector_type",
    "Injector Part Number": "injector_type",
    "Defective parts checked": "parts_checked",
    "Parts Checked": "parts_checked",
    "Status": "status",
    "NOK Count": "nok_count",
    "Total particle found": "total_particles",
    "Particle inside nozzle": "particle_nozzle",
    "Particle in Z hole": "particle_zhole",
    "Particle in A hole": "particle_ahole",
    "Particle Location": "particle_location",
    "Rejection Date": "rejection_date",
    "Rejection Shift": "rejection_shift",
    "Metallic/Non metallic": "metallic",
    "DA/Fresh": "da_fresh",
    "Chemistry": "chemistry",
    "Size": "size",
    "Defect Category": "defect_category",
    "Investigation Finding": "investigation_finding",
    "Investigation Days": "investigation_days",
}

OPERATOR_LABELS = {
    "eq": "equals",
    "equals": "equals",
    "neq": "does not equal",
    "not_equals": "does not equal",
    "gt": ">",
    ">": ">",
    "gte": ">=",
    ">=": ">=",
    "lt": "<",
    "<": "<",
    "lte": "<=",
    "<=": "<=",
    "contains": "contains",
    "not_contains": "does not contain",
    "in": "is one of",
    "is_empty": "is blank/empty",
    "not_empty": "is populated",
}


def resolve_record_field(rec: Dict[str, Any], field_name: str) -> Any:
    if field_name in rec:
        return rec[field_name]
    mapped = FIELD_ALIASES.get(field_name)
    if mapped and mapped in rec:
        return rec[mapped]
    raw = rec.get("raw", {})
    if isinstance(raw, dict) and field_name in raw:
        return raw[field_name]
    return ""


def evaluate_single_condition(rec: Dict[str, Any], field_name: str, operator: str, target_val: str) -> bool:
    actual = resolve_record_field(rec, field_name)
    op = (operator or "eq").strip().lower()

    if op == "is_empty":
        return actual is None or str(actual).strip() == "" or str(actual).strip().lower() == "none"
    if op == "not_empty":
        return actual is not None and str(actual).strip() != "" and str(actual).strip().lower() != "none"

    if actual is None:
        return False

    # Attempt numeric comparison when both sides parse as numbers
    try:
        actual_num = float(actual)
        target_num = float(target_val)
        is_numeric = True
    except (ValueError, TypeError):
        is_numeric = False
        actual_num = 0.0
        target_num = 0.0

    actual_str = str(actual).strip().lower()
    target_str = str(target_val or "").strip().lower()

    if op in ("eq", "equals", "="):
        return (actual_num == target_num) if is_numeric else (actual_str == target_str)
    if op in ("neq", "not_equals", "!="):
        return (actual_num != target_num) if is_numeric else (actual_str != target_str)
    if op in ("gt", ">"):
        return is_numeric and (actual_num > target_num)
    if op in ("gte", ">="):
        return is_numeric and (actual_num >= target_num)
    if op in ("lt", "<"):
        return is_numeric and (actual_num < target_num)
    if op in ("lte", "<="):
        return is_numeric and (actual_num <= target_num)
    if op == "contains":
        return target_str in actual_str
    if op == "not_contains":
        return target_str not in actual_str
    if op == "in":
        allowed = [item.strip().lower() for item in target_str.split(",") if item.strip()]
        return actual_str in allowed

    return False


def record_matches_rule_conditions(rule: AlertRule, rec: Dict[str, Any]) -> bool:
    """Evaluates all AlertCondition rows on a rule against a single normalized record."""
    if rule.data_source and rule.data_source not in ("ALL", "") and rec.get("data_source") != rule.data_source:
        return False

    conditions: List[AlertCondition] = list(rule.conditions or [])
    if not conditions:
        return True

    # Group conditions by condition_group; inside each group use AND, combine groups by rule.logical_operator
    groups: Dict[int, List[bool]] = defaultdict(list)
    for cond in conditions:
        g_id = cond.condition_group or 1
        groups[g_id].append(evaluate_single_condition(rec, cond.field_name, cond.operator, cond.value))

    if len(groups) == 1:
        results = list(groups.values())[0]
        if (rule.logical_operator or "AND").upper() == "OR":
            return any(results)
        return all(results)

    group_outcomes = [all(res_list) for res_list in groups.values()]
    if (rule.logical_operator or "AND").upper() == "OR":
        return any(group_outcomes)
    return all(group_outcomes)


def build_human_readable_summary(rule: AlertRule, group_names_to: List[str], group_names_cc: List[str]) -> str:
    """Produces a clear plain-English description of what the rule does."""
    trigger_map = {
        "NOK_DETECTED": "a NOK / rejection record is detected",
        "FIRST_NOK_OF_DAY": "the first NOK record of the day occurs",
        "NOK_COUNT_THRESHOLD": f"NOK count is >= {int(rule.threshold_value or 2)}",
        "NOK_RATE_THRESHOLD": f"NOK rate exceeds {rule.threshold_value or 5.0}%",
        "PARTICLE_FOUND": "any particle contamination is found",
        "PARTICLE_COUNT_THRESHOLD": f"total particle count is >= {int(rule.threshold_value or 2)}",
        "PARTICLE_LOCATION": "a particle is observed at a specific critical location",
        "STATION_NOK": "a specific station produces a NOK record",
        "AUDITOR_NOK": "a specific auditor logs a NOK record",
        "CUSTOMER_NOK": "a specific customer/type generates a NOK record",
        "REPEATED_NOK_WINDOW": f"repeated NOK records (>= {int(rule.threshold_value or 3)}) occur",
        "SUDDEN_SPIKE": f"NOK count spikes by >= {rule.threshold_value or 50}% over baseline",
        "MISSING_UPDATE_DEADLINE": "no WSA analysis update is received by the configured deadline",
        "DAILY_SUMMARY": "the scheduled Daily Analysis Summary runs",
        "SHIFT_SUMMARY": "the scheduled Shift Summary runs",
        "ACTION_PLAN_FOLLOWUP": "a Gemba /NOK finding requires action-plan follow-up",
        "PENDING_INVESTIGATION_AGE": f"an investigation remains Pending beyond {int(rule.threshold_value or 3)} days",
        "CUSTOM_COMPOSITE": "custom composite conditions are satisfied",
    }
    base_phrase = trigger_map.get(rule.trigger_type, f"trigger '{rule.trigger_type}' fires")

    cond_phrases = []
    for c in rule.conditions or []:
        op_label = OPERATOR_LABELS.get(c.operator, c.operator)
        if c.operator in ("is_empty", "not_empty"):
            cond_phrases.append(f"{c.field_name} {op_label}")
        else:
            cond_phrases.append(f"{c.field_name} {op_label} '{c.value}'")

    joiner = f" {(rule.logical_operator or 'AND').upper()} "
    cond_str = f" where ({joiner.join(cond_phrases)})" if cond_phrases else ""

    window_str = ""
    if rule.time_window_hours:
        window_str += f" within {rule.time_window_hours:g}h"
    if rule.group_by_field:
        window_str += f" grouped by {rule.group_by_field}"

    to_str = ", ".join(group_names_to) if group_names_to else "configured recipients"
    cc_str = f" (CC: {', '.join(group_names_cc)})" if group_names_cc else ""

    return f"When {base_phrase}{cond_str}{window_str}, send a {rule.severity} email to {to_str}{cc_str}."


def evaluate_rule(
    rule: AlertRule,
    candidate_records: List[Dict[str, Any]],
    all_records: List[Dict[str, Any]],
    is_test: bool = False,
) -> Tuple[bool, str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Evaluates a single AlertRule against candidate (delta) records and full context records.
    Returns:
      (triggered: bool, reason: str, matched_records: List[Dict], metrics_summary: Dict)
    """
    # Filter validity date range if configured on rule
    today_iso = datetime.now().strftime("%Y-%m-%d")
    if not is_test:
        if rule.start_date and today_iso < rule.start_date:
            return False, "Rule start date not reached", [], {}
        if rule.end_date and today_iso > rule.end_date:
            return False, "Rule end date expired", [], {}

    ttype = (rule.trigger_type or "NOK_DETECTED").upper()
    threshold = rule.threshold_value if rule.threshold_value is not None else 1.0

    # For EVENT rules during normal execution, require at least one candidate delta record unless it's a scheduled/summary/deadline rule or a test run
    working_pool = all_records if (is_test or rule.rule_category == "SCHEDULED" or ttype in (
        "DAILY_SUMMARY", "SHIFT_SUMMARY", "MISSING_UPDATE_DEADLINE", "PENDING_INVESTIGATION_AGE", "ACTION_PLAN_FOLLOWUP"
    )) else candidate_records

    if not working_pool and not is_test:
        return False, "No new or changed records to evaluate", [], {}

    # Apply condition filters
    filtered_candidates = [r for r in working_pool if record_matches_rule_conditions(rule, r)]
    filtered_all = [r for r in all_records if record_matches_rule_conditions(rule, r)]

    # 1. Scheduled Daily / Shift Summary
    if ttype in ("DAILY_SUMMARY", "SHIFT_SUMMARY"):
        # Pick latest date present in dataset (or today)
        dated_Pool = [r for r in filtered_all if r.get("date_iso")]
        latest_date = max((r["date_iso"] for r in dated_Pool), default=today_iso)
        day_records = [r for r in filtered_all if r.get("date_iso") == latest_date] or filtered_all[:25]
        summary = compute_pool_summary(day_records)
        reason = (
            f"Scheduled {ttype.replace('_', ' ').title()} for {summary['date']}: "
            f"Analyzed {int(summary['parts_checked'])} parts, {summary['nok_count']} NOK ({summary['nok_rate']}%)."
        )
        return True, reason, day_records[:20], summary

    # 2. Missing Update Deadline
    if ttype == "MISSING_UPDATE_DEADLINE":
        today_recs = [r for r in all_records if r.get("date_iso") == today_iso]
        total_parts_today = sum(r.get("parts_checked", 0) for r in today_recs)
        if not today_recs or total_parts_today == 0:
            summary = compute_pool_summary(today_recs)
            summary["date"] = datetime.now().strftime("%d-%m-%Y")
            return True, f"No WSA analysis update or 0 parts checked recorded for {summary['date']} by deadline.", [], summary
        if is_test:
            summary = compute_pool_summary(today_recs or all_records[:5])
            return True, f"[Test Mode] Deadline check simulated ({len(today_recs)} records found today).", today_recs[:5], summary
        return False, "Analysis update already present for today", [], {}

    # 3. Pending Investigation Age / Action Plan Follow-up
    if ttype in ("PENDING_INVESTIGATION_AGE", "ACTION_PLAN_FOLLOWUP"):
        min_days = threshold if rule.threshold_value is not None else 3.0
        matched = [
            r for r in filtered_all
            if r.get("status") in ("PENDING", "NOK") and (r.get("investigation_days", 0) >= min_days or ttype == "ACTION_PLAN_FOLLOWUP")
        ]
        if matched:
            summary = compute_pool_summary(matched)
            reason = f"{len(matched)} case(s) require action-plan follow-up / pending resolution."
            return True, reason, matched[:15], summary
        return False, "No pending investigations exceeding threshold", [], {}

    # 4. Windowed / Grouped NOK Count or Repeated NOK
    if ttype in ("NOK_COUNT_THRESHOLD", "REPEATED_NOK_WINDOW"):
        min_noks = max(1, int(threshold if rule.threshold_value is not None else 2))
        nok_pool = [r for r in filtered_all if r.get("status") == "NOK"]
        group_field = FIELD_ALIASES.get(rule.group_by_field or "", rule.group_by_field or "station")
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in nok_pool:
            key = str(resolve_record_field(r, group_field) or "All")
            grouped[key].append(r)

        for g_key, recs in grouped.items():
            # Also ensure at least one record in this group is in candidate_records (unless test mode)
            has_fresh = is_test or any(r["record_key"] in {c["record_key"] for c in filtered_candidates} for r in recs)
            if has_fresh and len(recs) >= min_noks:
                summary = compute_pool_summary(recs)
                reason = f"{len(recs)} NOK records detected for {rule.group_by_field or 'Station'} '{g_key}' (Threshold >= {min_noks})."
                return True, reason, recs[:15], summary
        return False, f"NOK count below threshold ({min_noks})", [], {}

    # 5. NOK Rate Threshold (%)
    if ttype == "NOK_RATE_THRESHOLD":
        min_rate = float(threshold if rule.threshold_value is not None else 5.0)
        group_field = FIELD_ALIASES.get(rule.group_by_field or "", rule.group_by_field or "station")
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in filtered_all:
            key = str(resolve_record_field(r, group_field) or "All")
            grouped[key].append(r)

        for g_key, recs in grouped.items():
            has_fresh = is_test or any(r["record_key"] in {c["record_key"] for c in filtered_candidates} for r in recs)
            if not has_fresh:
                continue
            summary = compute_pool_summary(recs)
            if summary["nok_rate"] >= min_rate and summary["nok_count"] > 0:
                reason = f"NOK rate {summary['nok_rate']}% exceeds threshold {min_rate}% for '{g_key}'."
                return True, reason, [r for r in recs if r.get("status") == "NOK"][:15] or recs[:10], summary
        return False, f"NOK rate below {min_rate}%", [], {}

    # 6. Sudden Spike vs Baseline
    if ttype == "SUDDEN_SPIKE":
        spike_pct = float(threshold if rule.threshold_value is not None else 50.0)
        by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in filtered_all:
            d_key = r.get("date_iso") or r.get("date") or "Unknown"
            by_date[d_key].append(r)
        sorted_dates = sorted(k for k in by_date.keys() if k != "Unknown")
        if len(sorted_dates) >= 2:
            latest_d = sorted_dates[-1]
            prev_dates = sorted_dates[-6:-1]
            latest_noks = sum(1 for r in by_date[latest_d] if r.get("status") == "NOK")
            avg_prev = sum(sum(1 for r in by_date[d] if r.get("status") == "NOK") for d in prev_dates) / max(1, len(prev_dates))
            if latest_noks > 0 and (avg_prev == 0 or ((latest_noks - avg_prev) / avg_prev) * 100.0 >= spike_pct):
                matched = [r for r in by_date[latest_d] if r.get("status") == "NOK"]
                summary = compute_pool_summary(by_date[latest_d])
                reason = f"Sudden NOK spike on {latest_d}: {latest_noks} NOKs vs baseline average {avg_prev:.1f}."
                return True, reason, matched[:15], summary
        return False, "No statistical spike detected", [], {}

    # 7. Particle Count Threshold
    if ttype == "PARTICLE_COUNT_THRESHOLD":
        min_p = float(threshold if rule.threshold_value is not None else 1.0)
        matched = [r for r in filtered_candidates if r.get("total_particles", 0) >= min_p]
        if matched:
            summary = compute_pool_summary(matched)
            reason = f"Particle count threshold (>= {int(min_p)}) exceeded on {len(matched)} record(s)."
            return True, reason, matched[:15], summary
        return False, "No records exceeding particle threshold", [], {}

    # 8. Standard Record-Level Event Triggers (NOK_DETECTED, FIRST_NOK_OF_DAY, PARTICLE_FOUND, PARTICLE_LOCATION, STATION_NOK, AUDITOR_NOK, CUSTOMER_NOK, CUSTOM_COMPOSITE)
    if ttype in (
        "NOK_DETECTED",
        "FIRST_NOK_OF_DAY",
        "PARTICLE_FOUND",
        "PARTICLE_LOCATION",
        "STATION_NOK",
        "AUDITOR_NOK",
        "CUSTOMER_NOK",
    ):
        matched = [
            r for r in filtered_candidates
            if r.get("status") == "NOK" or r.get("total_particles", 0) > 0
        ]
    else:
        matched = filtered_candidates

    if matched:
        summary = compute_pool_summary(matched)
        first_rec = matched[0]
        reason = (
            f"Rule '{rule.name}' matched {len(matched)} record(s) "
            f"(Station: {first_rec.get('station') or 'N/A'}, Location: {first_rec.get('particle_location') or 'N/A'})."
        )
        return True, reason, matched[:15], summary

    return False, "Conditions not met on current records", [], {}


def compute_pool_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregates KPI context for email templates and Power Automate payloads."""
    if not records:
        return {
            "date": datetime.now().strftime("%d-%m-%Y"),
            "shift": "1st",
            "station": "Line 5",
            "auditor": "QMM2-NaP",
            "customer": "All",
            "injector_type": "-",
            "parts_checked": 0,
            "nok_count": 0,
            "ok_count": 0,
            "pending_count": 0,
            "nok_rate": 0.0,
            "total_particles": 0,
            "particle_location": "None",
            "rejection_date": "-",
            "rejection_shift": "-",
            "metallic": "-",
            "da_fresh": "-",
            "chemistry": "-",
            "size": "-",
        }

    # Prefer the first NOK record as the primary specimen for card fields
    nok_recs = [r for r in records if r.get("status") == "NOK"]
    primary = nok_recs[0] if nok_recs else records[0]

    total_parts = sum(float(r.get("parts_checked", 0) or 0) for r in records)
    nok_count = len(nok_recs)
    ok_count = sum(1 for r in records if r.get("status") == "OK")
    pending_count = sum(1 for r in records if r.get("status") == "PENDING")
    total_particles = sum(float(r.get("total_particles", 0) or 0) for r in records)
    nok_rate = round((nok_count / total_parts) * 100.0, 2) if total_parts > 0 else (
        round((nok_count / len(records)) * 100.0, 2) if records else 0.0
    )

    locations = sorted({
        str(r.get("particle_location", "")).strip()
        for r in (nok_recs or records)
        if r.get("particle_location") and str(r.get("particle_location")).lower() not in ("none", "")
    })

    return {
        "date": primary.get("date") or datetime.now().strftime("%d-%m-%Y"),
        "shift": primary.get("shift") or "1st",
        "station": primary.get("station") or "Line 5",
        "auditor": primary.get("auditor") or "PS/QMM2-NaP",
        "customer": primary.get("customer") or "CRIN",
        "injector_type": primary.get("injector_type") or "0445120568",
        "parts_checked": int(total_parts) if float(total_parts).is_integer() else round(total_parts, 2),
        "nok_count": nok_count,
        "ok_count": ok_count,
        "pending_count": pending_count,
        "nok_rate": nok_rate,
        "total_particles": int(total_particles) if float(total_particles).is_integer() else round(total_particles, 2),
        "particle_location": ", ".join(locations) if locations else "No Particle found",
        "rejection_date": primary.get("rejection_date") or primary.get("date") or "-",
        "rejection_shift": primary.get("rejection_shift") or primary.get("shift") or "-",
        "metallic": primary.get("metallic") or "-",
        "da_fresh": primary.get("da_fresh") or "-",
        "chemistry": primary.get("chemistry") or "-",
        "size": primary.get("size") or "-",
        "investigation_finding": primary.get("investigation_finding") or "",
    }
