import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from backend.alerts.models import AlertConfiguration, AlertDelivery, AlertRule


def get_effective_webhook_url(db: Session, rule: Optional[AlertRule] = None) -> str:
    """Resolves the Power Automate webhook URL from rule override, environment variable, or DB config."""
    if rule and rule.webhook_url_override and rule.webhook_url_override.strip():
        return rule.webhook_url_override.strip()

    env_url = os.environ.get("WSA_POWER_AUTOMATE_WEBHOOK_URL", "").strip()
    if env_url:
        return env_url

    cfg = db.query(AlertConfiguration).first()
    if cfg and cfg.power_automate_webhook_url and cfg.power_automate_webhook_url.strip():
        return cfg.power_automate_webhook_url.strip()

    return ""


def send_webhook_payload(
    webhook_url: str,
    payload: Dict[str, Any],
    secret_header_name: str = "X-WSA-Secret-Token",
    secret_header_value: str = "",
    timeout_seconds: int = 10,
) -> Tuple[bool, int, str]:
    """
    Dispatches the structured JSON payload to a Power Automate HTTP webhook trigger.
    Returns (success: bool, http_status: int, message: str).
    """
    if not webhook_url:
        return False, 0, "No Power Automate webhook URL configured (queued for poll or awaiting URL)."

    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "WSA-Quality-Alert-Engine/2.0",
    }
    secret_val = os.environ.get("WSA_ALERT_SECRET_TOKEN", "").strip() or secret_header_value.strip()
    if secret_header_name and secret_val:
        headers[secret_header_name] = secret_val

    req = urllib.request.Request(webhook_url, data=data_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status_code = resp.getcode()
            resp_body = resp.read().decode("utf-8", errors="ignore")[:500]
            if 200 <= status_code < 300:
                return True, status_code, resp_body or "Accepted by Power Automate"
            return False, status_code, f"Unexpected HTTP {status_code}: {resp_body}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")[:500] if e.fp else str(e)
        return False, e.code, f"HTTP {e.code}: {err_body}"
    except Exception as exc:
        return False, 0, f"Connection error: {str(exc)}"


def attempt_delivery(db: Session, delivery: AlertDelivery, rule: Optional[AlertRule] = None) -> bool:
    """
    Attempts to deliver an AlertDelivery via Power Automate webhook if a URL is configured.
    If no webhook URL is set, keeps the delivery in QUEUED state so Power Automate can poll `/api/alerts/poll`
    or marks it DELIVERED (Simulated/Poll-Ready) during local testing if requested.
    """
    cfg = db.query(AlertConfiguration).first()
    webhook_url = get_effective_webhook_url(db, rule)
    now = datetime.utcnow()
    delivery.last_attempt_at = now

    try:
        payload = json.loads(delivery.payload_json or "{}")
    except Exception:
        payload = {}

    if not webhook_url:
        # No outbound webhook URL configured: leave in QUEUED for Power Automate polling
        delivery.status = "QUEUED"
        delivery.error_message = "Ready for Power Automate poll (or configure outbound Webhook URL in System Health)."
        db.commit()
        return True

    delivery.status = "SENDING"
    db.commit()

    ok, status_code, msg = send_webhook_payload(
        webhook_url=webhook_url,
        payload=payload,
        secret_header_name=(cfg.secret_header_name if cfg else "X-WSA-Secret-Token"),
        secret_header_value=(cfg.secret_header_value if cfg else ""),
    )

    delivery.http_status_code = status_code
    if ok:
        delivery.status = "DELIVERED"
        delivery.delivered_at = now
        delivery.error_message = ""
        if cfg:
            cfg.last_webhook_success_at = now
            cfg.last_webhook_error = ""
        db.commit()
        return True
    else:
        delivery.retry_count = (delivery.retry_count or 0) + 1
        delivery.error_message = msg
        backoff_sec = (rule.retry_backoff_seconds if rule and rule.retry_backoff_seconds else 60) * max(1, delivery.retry_count)
        if delivery.retry_count <= (delivery.max_retries or 3):
            delivery.status = "QUEUED"
            delivery.next_retry_at = now + timedelta(seconds=backoff_sec)
        else:
            delivery.status = "FAILED"
            delivery.next_retry_at = None
        if cfg:
            cfg.last_webhook_error = f"{now.strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
        db.commit()
        return False
