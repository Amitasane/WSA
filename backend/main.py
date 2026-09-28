import os
import io
import csv
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.database import engine, Base, get_db
from backend import models
from backend.auth import authenticate_user, create_user, get_current_user
from backend.investigation_loader import (
    get_cached_investigation_data,
    reload_investigation_data,
    get_excel_file_path,
    get_available_sources,
    get_active_source_info,
    set_active_source,
    BOSCH_NETWORK_PATH,
)

from backend.investigation_analytics import (
    filter_investigation_records,
    calculate_kpis,
    get_monthly_trend,
    get_pareto_defects,
    get_customer_breakdown,
    get_product_share,
    get_analytics_breakdown,
)

app = FastAPI(title="Investigation Dashboard")

# Static assets and template directory
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize database tables for authentication
Base.metadata.create_all(bind=engine)


# ================= AUTHENTICATION =================

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "show_header": True,
        "hide_home_icon": True,
    })


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password.",
            "show_header": True,
            "hide_home_icon": True,
        })

    response = RedirectResponse("/", status_code=302)
    response.set_cookie("user_id", str(user.id))
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "show_header": True,
        "hide_home_icon": True,
    })


@app.post("/register")
def register(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    department: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    error = create_user(
        db,
        first_name,
        last_name,
        username,
        email,
        password,
        confirm_password,
        department,
        role,
    )

    if error:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": error,
            "show_header": True,
            "hide_home_icon": True,
        })

    return RedirectResponse("/login", status_code=302)


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id")
    return response


# ================= DATA RELOAD & SOURCE MANAGEMENT =================

@app.get("/refresh-data")
def refresh_data(request: Request):
    """Explicitly re-reads the workbook and refreshes the in-memory cache."""
    try:
        get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    reload_investigation_data()
    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(referer, status_code=302)


@app.get("/set-source")
def switch_source_get(
    request: Request,
    source: str = Query("local"),
    custom_path: Optional[str] = Query(None),
):
    """Switch active data source between Local, Bosch Network Share, or Custom."""
    try:
        get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    set_active_source(source, custom_path)
    referer = request.headers.get("referer") or "/dashboard"
    base_url = referer.split("?")[0]
    return RedirectResponse(base_url, status_code=302)


@app.post("/set-source")
def switch_source_post(
    request: Request,
    source: str = Form("local"),
    custom_path: Optional[str] = Form(None),
):
    """Switch active data source via form submission."""
    try:
        get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    set_active_source(source, custom_path)
    referer = request.headers.get("referer") or "/dashboard"
    base_url = referer.split("?")[0]
    return RedirectResponse(base_url, status_code=302)


# ================= HOME =================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    return templates.TemplateResponse("home.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
    })



# ================= DASHBOARD =================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    product_class: Optional[str] = Query(None),
    month: Optional[str] = Query(None),
    customer: Optional[str] = Query(None),
    complaint_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    all_records = data["records"]

    # Apply filters
    filtered_records = filter_investigation_records(
        all_records,
        product_class=product_class,
        month=month,
        customer=customer,
        complaint_type=complaint_type,
        outcome=outcome,
    )

    # Compute quality metrics and chart datasets
    kpis = calculate_kpis(filtered_records)
    trend_data = get_monthly_trend(filtered_records)
    pareto_data = get_pareto_defects(filtered_records)
    customer_data = get_customer_breakdown(filtered_records, limit=10)
    product_share = get_product_share(filtered_records)

    # Recent 10 technical investigations
    recent_records = filtered_records[:10]

    source_path = get_excel_file_path()
    source_filename = os.path.basename(source_path)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "source_filename": source_filename,
        "source_error": data["error"],
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
        "kpis": kpis,

        "trend_data": trend_data,
        "pareto_data": pareto_data,
        "customer_data": customer_data,
        "product_share": product_share,
        "recent_records": recent_records,
        "active_filters": {
            "product_class": product_class,
            "month": month,
            "customer": customer,
            "complaint_type": complaint_type,
            "outcome": outcome,
        },
        "filter_options": {
            "months": data["months"],
            "customers": data["customers"],
            "complaint_types": data["complaint_types"],
        },
    })


# ================= VIEW RECORDS =================

@app.get("/view", response_class=HTMLResponse)
def view_records(
    request: Request,
    product_class: Optional[str] = Query(None),
    month: Optional[str] = Query(None),
    customer: Optional[str] = Query(None),
    complaint_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=10, le=100),
):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    all_records = data["records"]

    filtered = filter_investigation_records(
        all_records,
        product_class=product_class,
        month=month,
        customer=customer,
        complaint_type=complaint_type,
        outcome=outcome,
        search=search,
    )

    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + page_size - 1) // page_size)
    current_page = min(page, total_pages)

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    paged_records = filtered[start_idx:end_idx]

    return templates.TemplateResponse("view_records.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "records": paged_records,
        "total_filtered": total_filtered,
        "total_unfiltered": len(all_records),
        "current_page": current_page,
        "total_pages": total_pages,
        "page_size": page_size,
        "source_error": data["error"],
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
        "filters": {

            "product_class": product_class,
            "month": month,
            "customer": customer,
            "complaint_type": complaint_type,
            "outcome": outcome,
            "search": search,
        },
        "filter_options": {
            "months": data["months"],
            "customers": data["customers"],
            "complaint_types": data["complaint_types"],
        },
    })


# ================= ANALYTICS =================

AVAILABLE_DIMENSIONS = [
    "Customer",
    "Defect Category",
    "Complaint Type",
    "Product Line",
    "Month",
    "Injector Part Number",
    "Plant",
    "Responsibility",
]

@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(
    request: Request,
    group_by: str = Query("Customer"),
    product_class: Optional[str] = Query(None),
    month: Optional[str] = Query(None),
    complaint_type: Optional[str] = Query(None),
):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    all_records = data["records"]

    filtered = filter_investigation_records(
        all_records,
        product_class=product_class,
        month=month,
        complaint_type=complaint_type,
    )

    kpis = calculate_kpis(filtered)
    analytics_breakdown = get_analytics_breakdown(filtered, group_by=group_by)

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "source_error": data["error"],
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
        "active_group_by": group_by,

        "available_dimensions": AVAILABLE_DIMENSIONS,
        "kpis": kpis,
        "analytics_data": analytics_breakdown,
        "filters": {
            "product_class": product_class,
            "month": month,
            "complaint_type": complaint_type,
        },
        "filter_options": {
            "months": data["months"],
            "complaint_types": data["complaint_types"],
        },
    })


@app.post("/analytics")
def analytics_post(
    request: Request,
    group_by: str = Form("Customer"),
    product_class: Optional[str] = Form(None),
    month: Optional[str] = Form(None),
    complaint_type: Optional[str] = Form(None),
):
    query_params = []
    if group_by:
        query_params.append(f"group_by={group_by}")
    if product_class:
        query_params.append(f"product_class={product_class}")
    if month:
        query_params.append(f"month={month}")
    if complaint_type:
        query_params.append(f"complaint_type={complaint_type}")
    
    url = "/analytics"
    if query_params:
        url += "?" + "&".join(query_params)
    return RedirectResponse(url, status_code=302)


# ================= OBSERVATIONS =================

@app.get("/observations", response_class=HTMLResponse)
def observations(
    request: Request,
    search: Optional[str] = Query(None),
    defect_category: Optional[str] = Query(None),
    product_class: Optional[str] = Query(None),
    customer: Optional[str] = Query(None),
):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    all_records = data["records"]

    filtered = filter_investigation_records(
        all_records,
        search=search,
        defect_category=defect_category,
        product_class=product_class,
        customer=customer,
    )

    kpis = calculate_kpis(filtered)
    particle_findings = sum(
        1 for r in filtered
        if "particle" in r["defect_category"].lower() or r["particle_location"]
    )

    return templates.TemplateResponse("observations.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "source_error": data["error"],
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
        "observations": filtered,
        "total_observations": len(filtered),
        "kpis": kpis,
        "particle_findings": particle_findings,
        "filters": {
            "search": search,
            "defect_category": defect_category,
            "product_class": product_class,
            "customer": customer,
        },
        "filter_options": {
            "defect_categories": data["defect_categories"],
            "customers": data["customers"],
        },
    })


# ================= REPORTS & EXPORT =================

@app.get("/download", response_class=HTMLResponse)
def download_page(request: Request):
    try:
        user = get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    source_filename = os.path.basename(get_excel_file_path())

    return templates.TemplateResponse("download.html", {
        "request": request,
        "show_header": True,
        "user": user,
        "total_rows": data["total_records"],
        "source_filename": source_filename,
        "source_error": data["error"],
        "active_source": get_active_source_info(),
        "available_sources": get_available_sources(),
        "filter_options": {

            "months": data["months"],
            "customers": data["customers"],
            "complaint_types": data["complaint_types"],
        },
    })


@app.post("/download")
def download_file(
    request: Request,
    format: str = Form("csv"),
    product_class: str = Form("All"),
    month: str = Form("All"),
    customer: str = Form("All"),
    complaint_type: str = Form("All"),
    outcome: str = Form("All"),
):
    try:
        get_current_user(request)
    except Exception:
        return RedirectResponse("/login")

    data = get_cached_investigation_data()
    filtered = filter_investigation_records(
        data["records"],
        product_class=product_class,
        month=month,
        customer=customer,
        complaint_type=complaint_type,
        outcome=outcome,
    )

    export_headers = [
        "Product Class",
        "Month Code",
        "Month Label",
        "Customer Complaint No",
        "Customer",
        "Complaint Type",
        "Injector Part Number",
        "Quantity",
        "Reported Complaint",
        "Technical Finding",
        "Defect Category",
        "Quality Outcome",
        "Investigation Status",
        "Serial Number",
        "MFD Code",
        "Vehicle Mileage",
        "QC Notification No",
        "ESN",
        "Particle Location",
        "Responsibility",
        "Manufacturing Plant",
        "For Analysis",
    ]

    export_rows = []
    for r in filtered:
        export_rows.append([
            r["product_class"],
            r["month_code"],
            r["month_label"],
            r["customer_complaint_no"],
            r["customer"],
            r["complaint_type"],
            r["injector_number"],
            r["qty"],
            r["complaint"],
            r["investigation_finding"],
            r["defect_category"],
            r["outcome"],
            r["status"],
            r["serial_no"],
            r["mfd"],
            r["mileage"],
            r["qc_number"],
            r["esn"],
            r["particle_location"],
            r["responsibility"],
            r["mfg_plant"],
            r["for_analysis"],
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format.lower() == "xlsx":
        # Native Excel export using openpyxl
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Investigations Export"

        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0A1F44", end_color="0A1F44", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        ws.append(export_headers)
        for col_idx in range(1, len(export_headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        data_font = Font(name="Segoe UI", size=10)
        for row_data in export_rows:
            ws.append(row_data)
            current_row = ws.max_row
            for col_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.font = data_font
                cell.border = thin_border

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"investigation_records_{timestamp}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    else:
        # CSV Export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(export_headers)
        writer.writerows(export_rows)

        output.seek(0)
        filename = f"investigation_records_{timestamp}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )