import os
import time
import threading
from datetime import datetime
from typing import Dict, Optional

from backend.database import SessionLocal
from backend.alerts import service, change_detector, models

_SCHEDULER_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()
_LAST_MTIMES: Dict[str, float] = {}
_LAST_SCHEDULED_RUN_MINUTE: str = ""


def _check_excel_mtimes() -> bool:
    """Returns True if 'CRIN Line rejection analysis updated.xlsx' was modified since last check."""
    changed = False
    path = change_detector.find_particle_workbook_path()
    if path and os.path.exists(path):
        try:
            mtime = os.path.getmtime(path)
            prev = _LAST_MTIMES.get(path)
            _LAST_MTIMES[path] = mtime
            if prev is not None and mtime > prev:
                changed = True
        except Exception:
            pass
    return changed


def _run_scheduled_rules_if_due(db) -> None:
    """Fires SCHEDULED rules whose schedule_time (HH:MM) matches current local time."""
    global _LAST_SCHEDULED_RUN_MINUTE
    now = datetime.now()
    hh_mm = now.strftime("%H:%M")
    day_abbr = now.strftime("%a")  # Mon, Tue, ...

    if hh_mm == _LAST_SCHEDULED_RUN_MINUTE:
        return

    scheduled_rules = (
        db.query(models.AlertRule)
        .filter(
            models.AlertRule.is_enabled == True,
            models.AlertRule.rule_category == "SCHEDULED",
        )
        .all()
    )

    any_due = False
    for r in scheduled_rules:
        if not r.schedule_time:
            continue
        days_allowed = [d.strip()[:3].lower() for d in (r.schedule_days or "").split(",") if d.strip()]
        if days_allowed and day_abbr.lower() not in days_allowed:
            continue
        if r.schedule_time.strip() == hh_mm:
            any_due = True
            break

    if any_due:
        _LAST_SCHEDULED_RUN_MINUTE = hh_mm
        service.run_evaluation_cycle(db, force_evaluate_all=False, include_scheduled=True)


def _scheduler_loop() -> None:
    while not _STOP_EVENT.is_set():
        try:
            db = SessionLocal()
            try:
                # 1. Process any due webhook retries
                service.process_pending_retries(db)

                # 2. Check if Excel files changed on disk
                if _check_excel_mtimes():
                    service.run_evaluation_cycle(db, force_evaluate_all=False, include_scheduled=False)

                # 3. Check time-based SCHEDULED rules
                _run_scheduled_rules_if_due(db)
            finally:
                db.close()
        except Exception:
            pass

        _STOP_EVENT.wait(30.0)


def start_background_scheduler() -> None:
    """Starts the non-blocking daemon thread for Excel change detection, scheduled rules, and retries."""
    global _SCHEDULER_THREAD
    if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
        return
    _STOP_EVENT.clear()
    _check_excel_mtimes()
    _SCHEDULER_THREAD = threading.Thread(target=_scheduler_loop, name="WSAAlertScheduler", daemon=True)
    _SCHEDULER_THREAD.start()
