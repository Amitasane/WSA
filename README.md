# Investigation Dashboard

An industrial-grade manufacturing quality and root-cause analysis web application built for Bosch Common Rail Injector (CRI & CRIN) rejection and field return investigations.

---

## 1. Project Overview

The **Investigation Dashboard** is an engineering monitoring and analytics platform that reads master investigation records directly from the 2026 rejection analysis workbook:

```text
2026(3) - Investigation Dashboard updated.xlsx
```

The application processes granular technical teardown observations, failure symptoms, and quality conformance decisions across **275 verified investigation cases** throughout 2026, covering **14 automotive and industrial OEMs** and **70 unique injector part numbers**.

---

## 2. Architecture & Data Flow

```text
Excel Workbook (2026(3) - Investigation Dashboard updated.xlsx)
                          ↓
      InvestigationLoader (backend/investigation_loader.py)
                          ↓
    Data Cleaning, Date Normalization & Defect Categorization
                          ↓
           In-Memory Cache (Thread-Safe Reloadable)
                          ↓
    InvestigationAnalytics (backend/investigation_analytics.py)
                          ↓
        FastAPI Web Application (backend/main.py)
                          ↓
    Jinja2 Templates + Chart.js + Bosch Visual Identity
```

---

## 3. Data Structure & Verified Schema

The application loads and normalizes records from the two primary investigation worksheets:

| Sheet | Records | Description | Typical Application |
| :--- | :--- | :--- | :--- |
| **`CRI`** | 183 | Common Rail Injectors | Passenger cars & light commercial vehicles |
| **`CRIN`** | 92 | Common Rail Injectors - Commercial | Medium & heavy commercial vehicles / off-highway |

### Core Data Fields
- **Product Class:** `CRI` or `CRIN`
- **Customer Complaint Number:** Unique tracking code (e.g., `CRI.I.26.01`, `CRIN.I.26.01`)
- **Customer:** OEM identifier (`M&M`, `TCL`, `TML`, `VECV`, `AL`, `ISUZU`, `SMLI`, `TTF`, `KOEL`, `CNHI`, `FUSO`, etc.)
- **Month:** Normalized calendar month (`Jan 2026` through `Sep 2026`) with chronological sorting
- **Complaint Type:** `0 Km` (Assembly line / pre-delivery), `Field` (In-service warranty), `AIS`
- **Injector Part Number:** Bosch part number (e.g., `0445111091`, `0445120568`)
- **Quantity (`Qty`):** Number of injectors inspected (sum = 475 parts)
- **Reported Symptom (`Complaint`):** Customer defect symptom (e.g., *Starting Problem*, *Excess Smoke*, *Engine Knocking*, *Fuel from Exhaust*, *Dribbling*)
- **Technical Investigation Finding (`Investigation Finding`):** Detailed laboratory teardown observation
- **Serial Number & MFD:** Unit serial number and Julian manufacturing date code (e.g., `53926`, `57927`)
- **Mileage:** Vehicle distance at failure (e.g., `0 Kms`, `12438 Kms`, `726 Kms`)
- **QC Notification Number:** SAP QMM notification identifier (e.g., `230007003678`)
- **Particle Location:** Specific component area (e.g., *Z hole*, *Nozzle seat*, *Inside body*)
- **Responsibility & Plant:** Where assigned (`C` = Customer, `B` = Bosch, `O` = OEM, `S` = Supplier; Plants: `CtP`, `NaP`, `HoP`, `RBCD`)

### Quality Status & Defect Categorization Rules
- **Completed:** Investigation finding is documented (198 records)
- **Pending:** Investigation in progress / teardown pending (77 records)
- **Quality Outcome:**
  - `Conforming to Specifications`: Injector conformed to Bosch manufacturing specifications / passed test (43 records)
  - `Defect Identified`: Non-conformance or defect confirmed (155 records)
  - `Pending`: Teardown in progress (77 records)
- **Defect Categories:**
  1. *Particle at Z-Hole* (#1 failure contributor — 59 cases)
  2. *Nozzle Area Particle / Defect* (16 cases)
  3. *Fuel Contamination* (14 cases)
  4. *Magnet / Coil Defect* (12 cases)
  5. *External Tampering / Handling* (8 cases)
  6. *Crack / Stress Corrosion* (2 cases)
  7. *Other Mechanical / Material Finding* (44 cases)
  8. *Conforming to Specifications* (43 cases)
  9. *Pending / In Analysis* (77 cases)
- **Defect Rate Calculation:**
  $$\text{Defect Rate (\%)} = \frac{\text{Defect Cases}}{\text{Completed Cases}} \times 100$$

---

## 4. Application Modules

### 1. Dashboard (`/dashboard`)
- Live KPI cards: Total Investigations, Parts Inspected, Defect Cases, Conforming Cases, Pending Cases, and Defect Rate (%).
- Dynamic multi-dimensional filter bar (Product Class, Month, Customer, Complaint Type, Outcome).
- Monthly Trend Chart: Total Investigations vs Defect Identified vs Conforming (OK).
- Defect Pareto Chart: Failure causes ranked with cumulative percentage curve (80/20 rule).
- Customer Spread Bar Chart: Total investigations vs defect cases per OEM.
- Product Mix Doughnut: CRI vs CRIN share.
- Recent Findings Table: Quick view of the latest 10 technical teardown records.

### 2. View Records (`/view`)
- Search across all fields (Customer, Complaint Number, Part Number, Symptom, Finding, Serial No).
- Multi-column filtering by Product Line, Month, Customer, Complaint Type, and Outcome.
- Server-side pagination (25, 50, 100 per page) and sorting.
- Exact source columns preserved with status pills (`Defect`, `Conforming`, `Pending`).
- Responsive horizontal table scrolling with sticky headers.

### 3. Analytics (`/analytics`)
- Selectable grouping dimensions:
  - *Customer*
  - *Defect Category*
  - *Complaint Type*
  - *Product Line*
  - *Month*
  - *Injector Part Number*
  - *Plant*
  - *Responsibility*
- Interactive comparison charts: Volume (Parts Inspected) and Defect Rate (%) by group.
- Detailed summary breakdown table with total volume, completed cases, defect cases, conforming cases, defect rate %, and share of total investigations.

### 4. Observations (`/observations`)
- Dedicated engineering tear-down inspector.
- Free-text search across technical findings, failure symptoms, and particle locations.
- Categorized observation cards displaying customer symptoms, full engineering diagnosis text, particle locations, manufacturing plant, and responsibility codes.

### 5. Reports & Export (`/download`)
- Custom export respecting all active filters.
- Native Excel (`.xlsx`) export with styled navy headers, auto-fit column widths, and cell borders.
- Comma-Separated Values (`.csv`) export with full source columns and derived quality metrics.

### 6. Authentication (`/login`, `/register`, `/logout`)
- Secure SQLite-backed user authentication with bcrypt password hashing and session management.

---

## 5. Configuration & Setup

### Environment Variables
Configure the active Excel source workbook without modifying code:

| Variable | Description | Default Fallback |
| :--- | :--- | :--- |
| `INVESTIGATION_EXCEL_FILE` | Absolute path to the Excel workbook | `2026(3) - Investigation Dashboard updated.xlsx` (in repo root) |

**PowerShell Example:**
```powershell
$env:INVESTIGATION_EXCEL_FILE="C:\path\to\2026(3) - Investigation Dashboard updated.xlsx"
```

### Installation
```powershell
# 1. Clone repository and navigate to folder
cd WSA

# 2. Create and activate virtual environment (optional)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

### Starting the Application
```powershell
python -m uvicorn backend.main:app --reload
```

Then open in your browser:
```text
http://127.0.0.1:8000
```

Default credentials from the existing database can be used (e.g. `Amitqmm`), or register a new user on `/register`.

---

## 6. Verification & Automated Tests

Run the complete test suite:
```powershell
python test_investigation_app.py
```

This verifies:
- Workbook parsing and zero unmapped months
- Accurate KPI calculations against raw Excel data
- Pareto defect rankings and cumulative calculations
- All FastAPI endpoints (Dashboard, View Records, Analytics, Observations, Download, Refresh)
- CSV and native Excel export data integrity
