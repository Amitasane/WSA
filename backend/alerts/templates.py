import json
from typing import Dict, Any, List, Optional
from jinja2.sandbox import SandboxedEnvironment
from backend.alerts.models import AlertRule, EmailTemplate

_sandbox_env = SandboxedEnvironment(autoescape=True)

FIELD_DISPLAY_LABELS = {
    "date": "Date of Analysis",
    "shift": "Analysis Shift",
    "station": "Rejection Station",
    "auditor": "Auditor / Responsibility",
    "customer": "Customer",
    "injector_type": "Injector Type / Part No",
    "parts_checked": "Total Parts Checked",
    "nok_count": "NOK / Defect Parts",
    "nok_rate": "NOK Rate (%)",
    "total_particles": "Total Particles Found",
    "particle_location": "Particle Location",
    "rejection_date": "Rejection Date",
    "rejection_shift": "Rejection Shift",
    "metallic": "Metallic / Non-Metallic",
    "da_fresh": "DA / Fresh",
    "chemistry": "Chemistry",
    "size": "Particle Size",
}

SEVERITY_COLORS = {
    "INFO": {"bg": "#005691", "badge": "#e0f2fe", "text": "#0369a1"},
    "WARNING": {"bg": "#d97706", "badge": "#fef3c7", "text": "#b45309"},
    "CRITICAL": {"bg": "#be123c", "badge": "#ffe4e6", "text": "#be123c"},
}


def render_safe_string(template_str: str, context: Dict[str, Any]) -> str:
    if not template_str:
        return ""
    try:
        tmpl = _sandbox_env.from_string(template_str)
        return tmpl.render(**context)
    except Exception:
        return template_str


def render_alert_email(
    rule: AlertRule,
    template: Optional[EmailTemplate],
    summary: Dict[str, Any],
    matched_records: List[Dict[str, Any]],
    dashboard_url: str,
    trigger_reason: str,
) -> Dict[str, str]:
    """
    Renders subject, observation, required_action, and full Bosch MIS HTML email body
    modeled directly after the real 'CRIN - Line 5 internal rejection analysis MIS' thread.
    """
    severity = (rule.severity or "CRITICAL").upper()
    colors = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["CRITICAL"])

    ctx = {
        **summary,
        "rule_name": rule.name,
        "severity": severity,
        "trigger_reason": trigger_reason,
        "dashboard_link": dashboard_url,
        "dashboard_url": dashboard_url,
    }

    subj_tmpl = (
        rule.custom_subject
        or (template.subject_template if template else "")
        or "[{{severity}}] CRIN - Line 5 internal rejection analysis MIS — {{rule_name}}"
    )
    subject = render_safe_string(subj_tmpl, ctx)

    intro = render_safe_string(template.intro_text if template else "Dear Team,", ctx)

    default_obs = (
        "Today, we analyzed total {{parts_checked}} parts and observed {{total_particles}} particle(s) at the {{particle_location}} location of injector."
        if summary.get("nok_count", 0) > 0 or summary.get("total_particles", 0) > 0
        else "On {{date}} analyzed total {{parts_checked}} parts — No abnormality was observed."
    )
    obs_tmpl = (
        rule.custom_body
        or (template.observation_template if template and template.observation_template else "")
        or (template.body_template if template and template.body_template else "")
        or default_obs
    )
    observation_text = render_safe_string(obs_tmpl, ctx)

    default_action = (
        "All observations have been logged in WSA. Kindly review the rejection station ({{station}}) and share the corresponding action plan for the discussed points."
        if severity in ("CRITICAL", "WARNING") and summary.get("nok_count", 0) > 0
        else "For information and continuous quality monitoring."
    )
    act_tmpl = (template.action_template if template and template.action_template else "") or default_action
    action_text = render_safe_string(act_tmpl, ctx)

    footer_raw = (
        template.footer_text
        if template and template.footer_text
        else "Best regards,\nQuality Management Methods, Nozzles (PS/QMM2-NaP)\nBosch Limited | Post Box No:3000 | Hosur Road, Adugodi | Bengaluru-560030 | INDIA"
    )
    footer_html = "<br>".join(render_safe_string(footer_raw, ctx).splitlines())

    # Determine table fields to include in the Bosch MIS summary card
    table_fields = [
        "date",
        "shift",
        "station",
        "injector_type",
        "parts_checked",
        "nok_count",
        "nok_rate",
        "particle_location",
        "rejection_date",
        "rejection_shift",
    ]
    if template and template.table_fields_json:
        try:
            parsed = json.loads(template.table_fields_json)
            if isinstance(parsed, list) and parsed:
                table_fields = parsed
        except Exception:
            pass

    rows_html = ""
    for f_key in table_fields:
        label = FIELD_DISPLAY_LABELS.get(f_key, f_key.replace("_", " ").title())
        val = ctx.get(f_key, "-")
        if f_key == "nok_rate":
            val = f"{val}%"
        rows_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #d8e2ef;font-weight:600;color:#1e293b;width:42%;background:#f8fafc;">{label}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #d8e2ef;color:#0f172a;">{val}</td>
        </tr>
        """

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background-color:#f1f5f9;margin:0;padding:24px;color:#0f172a;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:6px;overflow:hidden;">
    <div style="background:{colors['bg']};color:#ffffff;padding:16px 22px;display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;opacity:0.9;">BOSCH | PS/QMM2-NaP QUALITY ALERT</div>
        <h2 style="margin:4px 0 0 0;font-size:19px;font-weight:700;">CRIN Line 5 – Internal Rejection Analysis</h2>
      </div>
      <span style="background:{colors['badge']};color:{colors['text']};padding:4px 10px;border-radius:4px;font-size:12px;font-weight:700;">{severity}</span>
    </div>

    <div style="padding:22px;">
      <p style="margin:0 0 12px 0;font-size:14px;">{intro}</p>
      <p style="margin:0 0 16px 0;font-size:15px;font-weight:600;color:#005691;">
        {ctx.get('date')} , Shift – {ctx.get('shift')} , {ctx.get('particle_location')}
      </p>

      <div style="background:#e8eef5;border:1px solid #b8c9de;border-radius:4px;padding:14px;margin-bottom:18px;">
        <div style="background:#1f4e79;color:#ffffff;padding:8px 12px;font-weight:700;font-size:14px;margin-bottom:10px;">
          WSA Analysis Summary — {rule.name}
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;background:#ffffff;">
          {rows_html}
        </table>
      </div>

      <div style="margin-bottom:14px;">
        <strong style="font-size:13px;color:#334155;text-transform:uppercase;">Observation:</strong>
        <p style="margin:4px 0 0 0;font-size:14px;line-height:1.5;background:#f8fafc;padding:10px 12px;border-left:4px solid {colors['bg']};">{observation_text}</p>
      </div>

      <div style="margin-bottom:20px;">
        <strong style="font-size:13px;color:#334155;text-transform:uppercase;">Required Action:</strong>
        <p style="margin:4px 0 0 0;font-size:14px;line-height:1.5;">{action_text}</p>
      </div>

      <div style="margin:20px 0;">
        <a href="{dashboard_url}" style="display:inline-block;background:#005691;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:4px;font-size:13px;font-weight:600;">
          Open WSA Investigation Dashboard →
        </a>
      </div>

      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <div style="font-size:12px;color:#64748b;line-height:1.5;">
        {footer_html}
      </div>
    </div>
  </div>
</body>
</html>"""

    return {
        "subject": subject,
        "observation": observation_text,
        "required_action": action_text,
        "body_html": html_body,
    }
