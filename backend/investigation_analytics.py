"""
Investigation Dashboard Analytics & Calculation Engine
Calculates KPIs, monthly trends, Pareto distributions, groupings, and multi-dimensional filters.
All metrics derive strictly from verified workbook fields.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict


def filter_investigation_records(
    records: List[Dict[str, Any]],
    product_class: Optional[str] = None,
    month: Optional[str] = None,
    complaint_type: Optional[str] = None,
    customer: Optional[str] = None,
    status: Optional[str] = None,
    outcome: Optional[str] = None,
    defect_category: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter investigation records by any combination of dimensions."""
    filtered = records

    if product_class and product_class not in ("All", "", "ALL"):
        p_upper = product_class.upper()
        filtered = [r for r in filtered if r["product_class"].upper() == p_upper]

    if month and month not in ("All", "", "ALL"):
        # Match either month_code (e.g., '2026-01') or month_label (e.g., 'Jan 2026')
        filtered = [
            r for r in filtered
            if r["month_code"] == month or r["month_label"] == month or r["month_raw"] == month
        ]

    if complaint_type and complaint_type not in ("All", "", "ALL"):
        c_upper = complaint_type.upper()
        filtered = [r for r in filtered if r["complaint_type"].upper() == c_upper]

    if customer and customer not in ("All", "", "ALL"):
        cust_upper = customer.upper()
        filtered = [r for r in filtered if r["customer"].upper() == cust_upper]

    if status and status not in ("All", "", "ALL"):
        st_upper = status.upper()
        filtered = [r for r in filtered if r["status"].upper() == st_upper]

    if outcome and outcome not in ("All", "", "ALL"):
        out_upper = outcome.upper()
        filtered = [r for r in filtered if r["outcome"].upper() == out_upper]

    if defect_category and defect_category not in ("All", "", "ALL"):
        cat_lower = defect_category.lower()
        filtered = [r for r in filtered if r["defect_category"].lower() == cat_lower]

    if search and search.strip():
        q = search.strip().lower()
        filtered = [
            r for r in filtered
            if (
                q in r["customer"].lower()
                or q in r["customer_complaint_no"].lower()
                or q in r["injector_number"].lower()
                or q in r["complaint"].lower()
                or q in r["investigation_finding"].lower()
                or q in r["serial_no"].lower()
                or q in r["qc_number"].lower()
                or q in r["particle_location"].lower()
                or q in r["defect_category"].lower()
            )
        ]

    return filtered


def calculate_kpis(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate high-level quality metrics:
      - Total Investigations (Count of complaint cases)
      - Total Parts Inspected (Sum of Qty)
      - Completed Investigations (Investigation Finding documented)
      - Pending Investigations (Under analysis)
      - Defect Cases (Non-conforming)
      - Conforming Cases (Passed specifications)
      - Defect Rate (%) = (Defect Cases / Completed Cases) * 100
      - Conformance Rate (%) = (Conforming Cases / Completed Cases) * 100
    """
    total = len(records)
    if total == 0:
        return {
            "total_investigations": 0,
            "total_parts": 0,
            "completed": 0,
            "pending": 0,
            "defect_cases": 0,
            "conforming_cases": 0,
            "defect_rate": 0.0,
            "conforming_rate": 0.0,
            "defect_parts": 0,
            "conforming_parts": 0,
            "unique_customers": 0,
            "unique_injectors": 0,
            "cri_count": 0,
            "crin_count": 0,
        }

    total_parts = sum(r["qty"] for r in records)
    completed = sum(1 for r in records if r["status"] == "Completed")
    pending = sum(1 for r in records if r["status"] == "Pending")
    defect_cases = sum(1 for r in records if r["outcome"] == "Defect Identified")
    conforming_cases = sum(1 for r in records if r["outcome"] == "Conforming to Specifications")

    defect_parts = sum(r["qty"] for r in records if r["outcome"] == "Defect Identified")
    conforming_parts = sum(r["qty"] for r in records if r["outcome"] == "Conforming to Specifications")

    defect_rate = round((defect_cases / completed * 100), 1) if completed > 0 else 0.0
    conforming_rate = round((conforming_cases / completed * 100), 1) if completed > 0 else 0.0

    unique_customers = len({r["customer"] for r in records if r["customer"]})
    unique_injectors = len({r["injector_number"] for r in records if r["injector_number"]})
    cri_count = sum(1 for r in records if r["product_class"] == "CRI")
    crin_count = sum(1 for r in records if r["product_class"] == "CRIN")

    return {
        "total_investigations": total,
        "total_parts": total_parts,
        "completed": completed,
        "pending": pending,
        "defect_cases": defect_cases,
        "conforming_cases": conforming_cases,
        "defect_rate": defect_rate,
        "conforming_rate": conforming_rate,
        "defect_parts": defect_parts,
        "conforming_parts": conforming_parts,
        "unique_customers": unique_customers,
        "unique_injectors": unique_injectors,
        "cri_count": cri_count,
        "crin_count": crin_count,
    }


def get_monthly_trend(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates monthly trend series sorted chronologically."""
    month_data = defaultdict(lambda: {
        "total": 0,
        "completed": 0,
        "defect": 0,
        "conforming": 0,
        "pending": 0,
        "parts": 0,
        "label": "",
    })

    for r in records:
        code = r["month_code"]
        if code == "2026-00":
            continue
        m = month_data[code]
        m["label"] = r["month_label"]
        m["total"] += 1
        m["parts"] += r["qty"]
        if r["status"] == "Completed":
            m["completed"] += 1
        else:
            m["pending"] += 1
            
        if r["outcome"] == "Defect Identified":
            m["defect"] += 1
        elif r["outcome"] == "Conforming to Specifications":
            m["conforming"] += 1

    sorted_codes = sorted(month_data.keys())

    return {
        "labels": [month_data[c]["label"] for c in sorted_codes],
        "total": [month_data[c]["total"] for c in sorted_codes],
        "defect": [month_data[c]["defect"] for c in sorted_codes],
        "conforming": [month_data[c]["conforming"] for c in sorted_codes],
        "pending": [month_data[c]["pending"] for c in sorted_codes],
        "parts": [month_data[c]["parts"] for c in sorted_codes],
    }


def get_pareto_defects(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pareto analysis of identified failure modes.
    Ranks failure categories by frequency and computes cumulative percentage curve.
    """
    # Count failure causes (excluding Pending and Conforming for pure defect Pareto)
    defect_counts = defaultdict(int)
    for r in records:
        cat = r["defect_category"]
        if cat not in ("Pending / In Analysis", "Conforming to Specifications"):
            defect_counts[cat] += 1

    sorted_items = sorted(defect_counts.items(), key=lambda x: x[1], reverse=True)
    total_defects = sum(count for _, count in sorted_items)

    labels = []
    counts = []
    cumulative_pct = []
    running_sum = 0

    for cat, count in sorted_items:
        labels.append(cat)
        counts.append(count)
        running_sum += count
        pct = round((running_sum / total_defects * 100), 1) if total_defects > 0 else 0.0
        cumulative_pct.append(pct)

    return {
        "labels": labels,
        "counts": counts,
        "cumulative_pct": cumulative_pct,
        "total_defects": total_defects,
    }


def get_customer_breakdown(records: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    """Breakdown of investigations by top customers."""
    cust_data = defaultdict(lambda: {"total": 0, "defect": 0, "conforming": 0, "parts": 0})
    for r in records:
        c = r["customer"] or "Unspecified"
        cust_data[c]["total"] += 1
        cust_data[c]["parts"] += r["qty"]
        if r["outcome"] == "Defect Identified":
            cust_data[c]["defect"] += 1
        elif r["outcome"] == "Conforming to Specifications":
            cust_data[c]["conforming"] += 1

    sorted_cust = sorted(cust_data.items(), key=lambda x: x[1]["total"], reverse=True)[:limit]

    return {
        "labels": [c for c, _ in sorted_cust],
        "total": [d["total"] for _, d in sorted_cust],
        "defect": [d["defect"] for _, d in sorted_cust],
        "conforming": [d["conforming"] for _, d in sorted_cust],
        "parts": [d["parts"] for _, d in sorted_cust],
    }


def get_product_share(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CRI vs CRIN breakdown for doughnut chart."""
    cri_cases = sum(1 for r in records if r["product_class"] == "CRI")
    crin_cases = sum(1 for r in records if r["product_class"] == "CRIN")
    cri_parts = sum(r["qty"] for r in records if r["product_class"] == "CRI")
    crin_parts = sum(r["qty"] for r in records if r["product_class"] == "CRIN")

    return {
        "labels": ["CRI (Passenger / Light)", "CRIN (Commercial Vehicle)"],
        "cases": [cri_cases, crin_cases],
        "parts": [cri_parts, crin_parts],
    }


GROUP_FIELD_MAP = {
    "Customer": "customer",
    "Defect Category": "defect_category",
    "Complaint Type": "complaint_type",
    "Product Line": "product_class",
    "Month": "month_label",
    "Injector Part Number": "injector_number",
    "Plant": "mfg_plant",
    "Responsibility": "responsibility",
}


def get_analytics_breakdown(records: List[Dict[str, Any]], group_by: str) -> Dict[str, Any]:
    """
    Computes aggregated statistical breakdown for any supported dimension.
    Provides group name, volume, parts count, defect cases, conforming cases,
    defect rate, and share of total investigations.
    """
    field_key = GROUP_FIELD_MAP.get(group_by, "customer")
    total_all = len(records)

    groups = defaultdict(lambda: {
        "total": 0,
        "parts": 0,
        "completed": 0,
        "defect": 0,
        "conforming": 0,
        "pending": 0,
    })

    for r in records:
        val = r.get(field_key) or "Unassigned"
        g = groups[val]
        g["total"] += 1
        g["parts"] += r["qty"]
        if r["status"] == "Completed":
            g["completed"] += 1
        else:
            g["pending"] += 1
            
        if r["outcome"] == "Defect Identified":
            g["defect"] += 1
        elif r["outcome"] == "Conforming to Specifications":
            g["conforming"] += 1

    sorted_groups = sorted(groups.items(), key=lambda x: x[1]["total"], reverse=True)

    rows = []
    labels = []
    volume_data = []
    rate_data = []

    for name, stats in sorted_groups:
        total = stats["total"]
        completed = stats["completed"]
        defect = stats["defect"]
        conforming = stats["conforming"]
        pending = stats["pending"]
        parts = stats["parts"]

        defect_rate = round((defect / completed * 100), 1) if completed > 0 else 0.0
        share_pct = round((total / total_all * 100), 1) if total_all > 0 else 0.0

        rows.append({
            "group_name": name,
            "total_cases": total,
            "parts_inspected": parts,
            "completed": completed,
            "defect_cases": defect,
            "conforming_cases": conforming,
            "pending_cases": pending,
            "defect_rate": defect_rate,
            "share_pct": share_pct,
        })
        labels.append(name)
        volume_data.append(parts)
        rate_data.append(defect_rate)

    return {
        "group_by": group_by,
        "total_records": total_all,
        "rows": rows,
        "chart_labels": labels[:12],
        "volume_data": volume_data[:12],
        "rate_data": rate_data[:12],
    }
