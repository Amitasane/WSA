# Power Automate Integration for WSA Quality Alerts

This document explains how to set up the Power Automate flows to consume the new WSA Alert API and send emails.

## 1. NOK / Restricted Defect -> WSA Alert API -> Power Automate -> Outlook Email

This flow fetches newly generated alerts from the WSA backend and sends them to the appropriate recipients.

### Step-by-Step Flow Configuration

1. **Trigger:** `Recurrence`
   - Schedule it to run every **5 minutes** (or as desired).
2. **Action 1:** `HTTP`
   - **Method:** `POST`
   - **URI:** `http://<WSA_SERVER_IP>:8000/api/alerts/poll`
   - **Headers:** `Content-Type: application/json`
3. **Action 2:** `Parse JSON`
   - **Content:** `Body` from the HTTP action.
   - **Schema:** 
     ```json
     {
         "type": "array",
         "items": {
             "type": "object",
             "properties": {
                 "alert_id": { "type": "integer" },
                 "rule_name": { "type": "string" },
                 "severity": { "type": "string" },
                 "message": { "type": "string" },
                 "wsa_url": { "type": "string" }
             }
         }
     }
     ```
4. **Action 3:** `Apply to each`
   - **Input:** `Body` (the array of alerts from Parse JSON)
   - **Inside the loop:**
     1. **Action 3.1:** `Send an email (V2) - Office 365 Outlook`
        - **To:** `<Your Quality Team / Environment Variable>`
        - **Subject:** `[WSA Alert] - @{items('Apply_to_each')?['severity']} - @{items('Apply_to_each')?['rule_name']}`
        - **Body (HTML):**
          ```html
          <h2>WSA Quality Alert Triggered</h2>
          <p><b>Rule:</b> @{items('Apply_to_each')?['rule_name']}</p>
          <p><b>Severity:</b> @{items('Apply_to_each')?['severity']}</p>
          <p><b>Details:</b> @{items('Apply_to_each')?['message']}</p>
          <p><a href="@{items('Apply_to_each')?['wsa_url']}">View in WSA Dashboard</a></p>
          ```
     2. **Action 3.2:** `HTTP` (Mark as Sent)
        - **Method:** `POST`
        - **URI:** `http://<WSA_SERVER_IP>:8000/api/alerts/mark-sent/@{items('Apply_to_each')?['alert_id']}`
        - This acknowledges back to WSA so the alert isn't sent again.

## 2. Shift Summary -> Power Automate -> Outlook Email

For scheduled digest emails (e.g., end of shift), you do not need the rule engine to fire per-record. Instead, you can schedule a Power Automate flow to pull the regular analytics endpoint or a new `/api/alerts/digest` endpoint (to be added) and format it.

1. **Trigger:** `Recurrence`
   - Schedule for the exact times shifts end (e.g., 07:00, 15:00, 23:00).
2. **Action 1:** `HTTP`
   - **Method:** `GET`
   - **URI:** `http://<WSA_SERVER_IP>:8000/api/metrics/shift-summary`
3. **Action 2:** `Parse JSON` (Parse the KPI metrics)
4. **Action 3:** `Send an email (V2)`
   - Include the KPIs (NOK rate, Total Parts Checked, Top Defect Stations) in a nicely formatted HTML table.
