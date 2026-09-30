# Microsoft Power Automate Integration Guide — WSA Enterprise Quality Alert Engine

This document describes how to connect the **WSA Quality Alert & Notification Engine** to **Microsoft Power Automate** for automated Outlook email delivery across Bosch functional groups (`PS/QMM`, `NaP/MFC`, `NaP/MFN`, `NaP/TEF`, `PS-DC/ENI1`, and Management CC).

---

## 1. Supported Integration Modes

The WSA Alert Engine supports two enterprise integration patterns:

### Mode A — Outbound HTTPS Webhook Push (Recommended for Cloud / Hybrid Flows)
1. In Power Automate, create an **Automated cloud flow** with the trigger **"When an HTTP request is received"**.
2. Copy the generated HTTP POST URL and paste it into **WSA Admin Alert Center → System Health → Power Automate HTTP Webhook Trigger URL** (or set the `WSA_POWER_AUTOMATE_WEBHOOK_URL` environment variable).
3. Whenever an event or scheduled rule triggers, WSA pushes the structured JSON payload (including `recipients`, `cc_recipients`, `email_subject`, and `email_body_html`) directly to Power Automate with automatic retry and exponential backoff.

### Mode B — Polling via On-Premises Data Gateway (`POST /api/alerts/poll`)
1. Create a **Scheduled cloud flow** (e.g., every 2 minutes).
2. Add an **HTTP** action:
   * **Method:** `POST`
   * **URI:** `http://<WSA_HOST>:8080/api/alerts/poll`
3. Add an **Apply to each** loop over the returned JSON array:
   * **Action 1:** *Office 365 Outlook — Send an email (V2)*
     * **To:** `@{join(items('Apply_to_each')?['recipients'], ';')}`
     * **CC:** `@{join(items('Apply_to_each')?['cc_recipients'], ';')}`
     * **Subject:** `@{items('Apply_to_each')?['email_subject']}`
     * **Body:** `@{items('Apply_to_each')?['email_body_html']}`
   * **Action 2:** *HTTP — Acknowledge Delivery*
     * **Method:** `POST`
     * **URI:** `http://<WSA_HOST>:8080/api/alerts/delivery/@{items('Apply_to_each')?['delivery_id']}/ack`
     * **Body:** `{"status": "DELIVERED", "http_status_code": 200}`

---

## 2. Standardized JSON Payload Schema

```json
{
  "event_id": "evt_20260930113000_a1b2c3",
  "delivery_id": 1,
  "is_test": false,
  "rule_id": 1,
  "rule_name": "CRIN Line 5 — Z-Hole / Nozzle Particle Detected",
  "rule_category": "EVENT",
  "trigger_type": "PARTICLE_LOCATION",
  "severity": "CRITICAL",
  "triggered_at": "2026-09-30T11:30:00",
  "date": "17-09-2026",
  "shift": "1st",
  "station": "EMI",
  "auditor": "Shravani Pawar",
  "customer": "TML",
  "injector_type": "0445120568",
  "parts_checked": 48,
  "nok_count": 1,
  "nok_rate": 2.08,
  "total_particles": 1,
  "particle_location": "Z hole",
  "chemistry": "FeCr",
  "size": "420 um",
  "rejection_date": "16-09-2026",
  "rejection_shift": "2nd",
  "observation": "Today, we analyzed total 48 parts and observed 1 particle(s) at the Z hole location of injector (0445120568).",
  "required_action": "All observations have been logged in WSA for Rejection Station EMI. Kindly review and share the corresponding action plan.",
  "dashboard_url": "http://localhost:8080/observations",
  "recipients": ["Shums.Tabrez@de.bosch.com", "Manoj.Patil@in.bosch.com"],
  "cc_recipients": ["Ramesh.Saligrama@in.bosch.com", "Naveen.BV@in.bosch.com"],
  "bcc_recipients": [],
  "email_subject": "[CRITICAL] RE: CRIN - Line 5 internal rejection analysis MIS (17-09-2026 | EMI)",
  "email_body_html": "<!DOCTYPE html>..."
}
```
