# WSA (Within Shift Analysis)

## Project Overview
WSA (Within Shift Analysis) is a manufacturing quality-monitoring web application built around a live Bosch Excel source. The web interface reads the `Particle Summary` sheet from the master workbook and presents the same data through Dashboard, View Records, Analytics, Observations, and Reports & Export.

## Live Excel Source
The application reads this Bosch network workbook by default:

`\\bosch.com\dfsrb\DfsIN\LOC\Na\DS\QMM\02_Projects\04_QMM3_Common\08_Projects_GAs\03_LAC\2024 - Snehal Yelmalle\CRIN Internal Rejection Analysis\CRIN Line rejection analysis updated.xlsx`

Sheet used:

`Particle Summary`

The WSA modules use these exact master headings:

- Date
- Shift
- Auditor
- Type
- Customer
- Station
- Defective parts checked
- Particle inside nozzle
- Particle in Z hole
- Particle in A hole
- Total particle found
- Rejection Date
- Rejection Shift
- Metallic/Non metallic
- DA/Fresh
- Chemistry
- Size

### OK / NOK rule
- **NOK:** `Rejection Date` is filled.
- **OK:** `Rejection Date` is blank.

`NOK Rate` is calculated as `NOK Records / Defective parts checked × 100` for the selected dataset.

## Web Modules
### Dashboard
Live KPI cards, date/shift/auditor/type filters, daily trend, shift-wise NOK, station-wise NOK, recent NOK records, auditor activity, and a live Excel preview.

### View Records
Search and filter the master Excel rows. The page shows the exact Excel headings, plus a derived Status column.

### Analytics
Group the master data by an actual Excel field:
`Shift`, `Auditor`, `Type`, `Customer`, `Station`, `Rejection Shift`, `Metallic/Non metallic`, `DA/Fresh`, `Chemistry`, or `Size`.

The page separates:
- Parts Checked by Group
- NOK Rate by Group
- Analysis Breakdown table

### Observations
Excel-based rejection/particle review with search and filters across the master fields. It defaults to NOK observations but can be changed to All or OK.

### Reports & Export
Exports the master Excel fields to CSV with optional date range and status filtering. No legacy database case export is used.

## Authentication
The existing SQLite database is retained only for application login/registration. Record and quality data shown in the WSA modules are read from the live Excel workbook, not from legacy SQLite record/case tables.

## Technology Stack
- Python
- FastAPI
- Jinja2
- HTML5 / CSS3 / JavaScript
- OpenPyXL for Excel reading
- SQLAlchemy / SQLite for authentication data

## Project Structure
```text
WSA/
├── backend/
│   ├── auth.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── static/
│   ├── style.css
│   ├── dashboard.js
│   └── images/
├── templates/
├── requirements.txt
└── README_WSA.md
```

## How to Run on Windows
### 1. Open the project in VS Code
Open the folder containing `backend`, `templates`, `static`, and `requirements.txt`.

### 2. Create and activate the virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```powershell
python -m pip install -r requirements.txt
```

### 4. Start WSA
```powershell
python -m uvicorn backend.main:app --reload
```

For access from another PC on the same network:
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Then open:

`http://YOUR-PC-IP:8000`

## Local Testing Override
For a local test copy of the workbook, set `WSA_EXCEL_FILE` before starting the application. The Bosch network path remains the default source.

PowerShell example:
```powershell
$env:WSA_EXCEL_FILE="C:\path\to\CRIN Line rejection analysis updated.xlsx"
python -m uvicorn backend.main:app --reload
```

The project intentionally has no active **Add Record** workflow in the sidebar. The current version is read-only with respect to the master Excel record data so that the web application does not create conflicting database records.
