import json
from sqlalchemy.orm import Session
from backend.alerts import models, service

BOSCH_RECIPIENT_GROUPS = [
    {
        "name": "PS/QMM Quality Management (Line 5)",
        "department_code": "PS/QMM",
        "description": "Quality Management Methods & 0-km Analysis Associates (PS/QMM1-NaP, PS/QMM2-NaP, PS/QMM8-NaP)",
        "members": [
            ("Sunay.Patel@in.bosch.com", "Patel Sunay", "PS/QMM1-NaP"),
            ("saurabh.patil@in.bosch.com", "Patil Saurabh", "PS/QMM1-NaP"),
            ("Manoj.Patil@in.bosch.com", "Patil Manoj Rajmal", "PS/QMM2-NaP"),
            ("Ketan.Kamboj@in.bosch.com", "Kamboj Ketan", "PS/QMM2-NaP"),
            ("BhushanRamesh.Bhuyarkar@in.bosch.com", "Bhuyarkar Bhushan Ramesh", "PS/QMM1-NaP"),
            ("Aman.Kumawat@in.bosch.com", "Kumawat Aman", "PS/QMM2-NaP"),
            ("singhal.kp@in.bosch.com", "Singhal Kailash", "PS/QMM2-NaP"),
            ("Ratnesh.Pandey@in.bosch.com", "Pandey Ratnesh", "PS/QMM1-NaP"),
            ("jaywant.nagrale@in.bosch.com", "Nagrale Jaywant", "PS/QMM8-NaP"),
            ("Yogesh.Bodke@in.bosch.com", "Bodke Yogesh", "PS/QMM2-NaP"),
            ("fixed-term.Omkar.Gaidhani@in.bosch.com", "Gaidhani Omkar", "PS/QMM1-NaP"),
            ("fixed-term.Devendra.Narode@bcn.bosch.com", "Narode Devendra", "PS/QMM2-NaP"),
        ],
    },
    {
        "name": "NaP/MFC Line 5 Production",
        "department_code": "NaP/MFC",
        "description": "CRIN Line 5 Manufacturing & FLM Production Team (MFC1, MFC3, MFC11, MFC12)",
        "members": [
            ("Shums.Tabrez@de.bosch.com", "Shums Tabrez", "NaP/MFC1"),
            ("sayyed.sarfraz@in.bosch.com", "Sayyed S N", "NaP/MFC11"),
            ("Deepak.Fukatkar@in.bosch.com", "Fukatkar Deepak", "NaP/MFC12"),
            ("Akshay.Rekhate@in.bosch.com", "Rekhate Akshay", "NaP/MFC12"),
            ("Dhananjay.Sirsat@in.bosch.com", "Sirsat Dhananjay", "NaP/MFC3"),
            ("SnehalAshok.Ingale@in.bosch.com", "Ingale Snehal Ashokrao", "NaP/MFC"),
            ("PriyaAnil.Dhomase@in.bosch.com", "Dhomase Priya Anil", "NaP/MFC12"),
            ("Hitesh.Kukade@in.bosch.com", "Kukade Hitesh Narayanrao", "NaP/MFC12"),
            ("Shailesh.Patil@in.bosch.com", "Patil Shailesh", "NaP/MFC11"),
        ],
    },
    {
        "name": "NaP/MFN Nozzle Manufacturing",
        "department_code": "NaP/MFN",
        "description": "Nozzle Manufacturing & Assembly Specialists (MFN, MFN2, MFN22, MFN31, MFN32)",
        "members": [
            ("Pratik.Chhatwani@in.bosch.com", "Chhatwani Pratik", "NaP/MFN"),
            ("pankaj.katware@in.bosch.com", "Katware Pankaj", "NaP/MFN"),
            ("kiran.thakare@in.bosch.com", "Thakare Kiran", "NaP/MFN32"),
            ("Hrishikesh.Pawar@in.bosch.com", "Pawar Hrishikesh", "NaP/MFN22"),
            ("Zaid.Shaikh@in.bosch.com", "Shaikh Zaid", "NaP/MFN31"),
            ("sharma.pg@in.bosch.com", "Sharma Prashant", "NaP/MFN"),
            ("Sourabh.Mishra@in.bosch.com", "Mishra Sourabh", "NaP/MFN2"),
        ],
    },
    {
        "name": "NaP/TEF & Engineering (PS-DC/ENI1)",
        "department_code": "TEF/ENI1",
        "description": "Technical Functions & Product Engineering (TEF2, TEF10, TEF22, PS-DC/ENI1-IN)",
        "members": [
            ("ManojRamesh.Sheogekar@de.bosch.com", "Sheogekar Manoj", "NaP/TEF2"),
            ("vishal.shinde@in.bosch.com", "Shinde Vishal", "NaP/TEF2"),
            ("rakesh.chaudhary@in.bosch.com", "Chaudhary Rakesh", "PS-DC/ENI1-IN"),
            ("Avinash.Khairnar@in.bosch.com", "Khairnar Avinash", "PS-DC/ENI1-IN"),
            ("Parag.Ketkar@in.bosch.com", "Ketkar Parag", "NaP/OFE-PT"),
            ("Rohit.Deshmane@in.bosch.com", "Deshmane Rohit", "VM/PJ-PSML-PM"),
        ],
    },
    {
        "name": "Management & Plant Leadership (CC)",
        "department_code": "MGMT",
        "description": "Department Heads & Value Stream Management (typically CC'd on CRIN Line 5 MIS updates)",
        "members": [
            ("Ramesh.Saligrama@in.bosch.com", "Ramesh Saligrama", "NaP/PT"),
            ("Naveen.BV@in.bosch.com", "Naveen B V", "PS/QMM-NaP"),
            ("bhat.mc@in.bosch.com", "Bhat Mukund", "NaP/MFC-PJ-CRIN"),
            ("shirwadkar.rs@in.bosch.com", "Shirwadkar Rahul", "NaP/MFN"),
        ],
    },
]

BOSCH_DEFAULT_TEMPLATES = [
    {
        "name": "CRIN Line 5 — Particle / NOK Alert Card",
        "description": "Standard Bosch MIS alert layout when a particle or NOK defect is identified during WSA inspection.",
        "subject_template": "[{{severity}}] RE: CRIN - Line 5 internal rejection analysis MIS ({{date}} | {{station}})",
        "intro_text": "Dear Team,",
        "observation_template": "Today, we analyzed total {{parts_checked}} parts and observed {{total_particles}} particle(s) at the {{particle_location}} location of injector ({{injector_type}}).",
        "action_template": "All observations have been logged in WSA for Rejection Station {{station}} (Rejection Date: {{rejection_date}}, Shift: {{rejection_shift}}). Kindly review and share the corresponding action plan for the discussed points.",
        "table_fields": [
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
            "chemistry",
            "size",
        ],
        "is_default": True,
    },
    {
        "name": "CRIN Line 5 — Daily / Shift MIS Summary",
        "description": "Daily / Shift summary digest modeled on the recurring CRIN Line 5 internal rejection analysis MIS emails.",
        "subject_template": "RE: CRIN - Line 5 internal rejection analysis MIS — Daily Summary ({{date}})",
        "intro_text": "Dear Team,",
        "observation_template": "WSA - CRIN Line 5 internal rejection analysis: On {{date}} we have checked total = {{parts_checked}} parts. NOK cases = {{nok_count}} (NOK Rate: {{nok_rate}}%). Particle status: {{particle_location}}.",
        "action_template": "Summary generated automatically by WSA Quality Alert Engine. Click the dashboard link below to inspect detailed shift and station trends.",
        "table_fields": [
            "date",
            "shift",
            "station",
            "parts_checked",
            "nok_count",
            "nok_rate",
            "total_particles",
            "particle_location",
        ],
        "is_default": False,
    },
    {
        "name": "CRIN Line 5 — Gemba & Action-Plan Follow-up",
        "description": "Follow-up notification for unresolved NOK investigations or Gemba activity action plans.",
        "subject_template": "[{{severity}}] CRIN - Line 5 internal rejection analysis MIS — Action Plan Follow-Up ({{station}})",
        "intro_text": "Dear Team,",
        "observation_template": "We have completed the WSA / Gemba observation regarding the particle observed at {{particle_location}} (Station: {{station}}, Customer: {{customer}}).",
        "action_template": "All observations have been discussed with the respective FLM. Kindly share the corresponding corrective action plan and closure timeline.",
        "table_fields": [
            "date",
            "station",
            "customer",
            "injector_type",
            "particle_location",
            "nok_count",
            "auditor",
        ],
        "is_default": False,
    },
]


def ensure_alert_system_initialized(db: Session) -> None:
    """
    Ensures configuration, recipient groups, templates, default enterprise rules,
    and initial Excel baseline snapshot exist in the database.
    """
    service.get_or_create_config(db)

    # 1. Seed Recipient Groups & Recipients if none exist
    group_map = {}
    if db.query(models.RecipientGroup).count() == 0:
        recipient_cache = {}
        for g_data in BOSCH_RECIPIENT_GROUPS:
            grp = models.RecipientGroup(
                name=g_data["name"],
                department_code=g_data["department_code"],
                description=g_data["description"],
                is_active=True,
            )
            db.add(grp)
            db.flush()
            group_map[grp.name] = grp

            for email_addr, disp_name, dept in g_data["members"]:
                email_key = email_addr.lower().strip()
                rec_obj = recipient_cache.get(email_key)
                if not rec_obj:
                    rec_obj = db.query(models.Recipient).filter(models.Recipient.email == email_addr).first()
                if not rec_obj:
                    rec_obj = models.Recipient(
                        email=email_addr,
                        display_name=disp_name,
                        department=dept,
                        is_active=True,
                    )
                    db.add(rec_obj)
                    db.flush()
                    recipient_cache[email_key] = rec_obj

                db.add(models.GroupMembership(group_id=grp.id, recipient_id=rec_obj.id))
        db.commit()
    else:
        for g in db.query(models.RecipientGroup).all():
            group_map[g.name] = g

    # 2. Seed Email Templates if none exist
    tmpl_map = {}
    if db.query(models.EmailTemplate).count() == 0:
        for t_data in BOSCH_DEFAULT_TEMPLATES:
            tmpl = models.EmailTemplate(
                name=t_data["name"],
                description=t_data["description"],
                subject_template=t_data["subject_template"],
                intro_text=t_data["intro_text"],
                observation_template=t_data["observation_template"],
                action_template=t_data["action_template"],
                table_fields_json=json.dumps(t_data["table_fields"]),
                is_default=t_data["is_default"],
            )
            db.add(tmpl)
            db.flush()
            tmpl_map[tmpl.name] = tmpl
        db.commit()
    else:
        for t in db.query(models.EmailTemplate).all():
            tmpl_map[t.name] = t

    # 3. Seed Default Enterprise Alert Rules if none exist
    if db.query(models.AlertRule).count() == 0:
        t_nok = tmpl_map.get("CRIN Line 5 — Particle / NOK Alert Card")
        t_sum = tmpl_map.get("CRIN Line 5 — Daily / Shift MIS Summary")
        t_gemba = tmpl_map.get("CRIN Line 5 — Gemba & Action-Plan Follow-up")

        g_qmm = group_map.get("PS/QMM Quality Management (Line 5)")
        g_mfc = group_map.get("NaP/MFC Line 5 Production")
        g_mfn = group_map.get("NaP/MFN Nozzle Manufacturing")
        g_mgmt = group_map.get("Management & Plant Leadership (CC)")

        # Rule 1: Z-Hole / Critical Particle Detection
        r1 = models.AlertRule(
            name="CRIN Line 5 — Z-Hole / Nozzle Particle Detected",
            description="Immediate CRITICAL alert when a particle is observed at Z-hole, A-hole, or Inside Nozzle in Particle Summary.",
            is_enabled=True,
            priority=1,
            rule_category="EVENT",
            trigger_type="PARTICLE_LOCATION",
            data_source="PARTICLE_SUMMARY",
            severity="CRITICAL",
            logical_operator="AND",
            cooldown_minutes=60,
            template_id=t_nok.id if t_nok else None,
        )
        db.add(r1)
        db.flush()
        db.add(models.AlertCondition(rule_id=r1.id, field_name="Status", operator="eq", value="NOK"))
        db.add(models.AlertCondition(rule_id=r1.id, field_name="Total particle found", operator="gte", value="1"))
        if g_qmm:
            db.add(models.RuleRecipientAssignment(rule_id=r1.id, recipient_type="TO", group_id=g_qmm.id))
        if g_mfc:
            db.add(models.RuleRecipientAssignment(rule_id=r1.id, recipient_type="TO", group_id=g_mfc.id))
        if g_mgmt:
            db.add(models.RuleRecipientAssignment(rule_id=r1.id, recipient_type="CC", group_id=g_mgmt.id))

        # Rule 2: Repeated Station NOK Threshold
        r2 = models.AlertRule(
            name="Repeated NOK Threshold (>= 2 NOKs at Same Station)",
            description="Triggers when EMI Station, HD Station, or Visual Station accumulates 2 or more NOK records within a 4-hour window.",
            is_enabled=True,
            priority=2,
            rule_category="EVENT",
            trigger_type="REPEATED_NOK_WINDOW",
            data_source="PARTICLE_SUMMARY",
            severity="WARNING",
            logical_operator="AND",
            time_window_hours=4.0,
            threshold_value=2.0,
            group_by_field="Station",
            cooldown_minutes=120,
            template_id=t_nok.id if t_nok else None,
        )
        db.add(r2)
        db.flush()
        db.add(models.AlertCondition(rule_id=r2.id, field_name="Status", operator="eq", value="NOK"))
        if g_qmm:
            db.add(models.RuleRecipientAssignment(rule_id=r2.id, recipient_type="TO", group_id=g_qmm.id))
        if g_mfn:
            db.add(models.RuleRecipientAssignment(rule_id=r2.id, recipient_type="TO", group_id=g_mfn.id))

        # Rule 3: Scheduled Daily Line 5 Analysis MIS Summary
        r3 = models.AlertRule(
            name="Daily CRIN Line 5 Analysis MIS Summary (17:00)",
            description="Scheduled daily MIS email summarizing total parts checked and particle observations from Particle Summary.",
            is_enabled=True,
            priority=5,
            rule_category="SCHEDULED",
            trigger_type="DAILY_SUMMARY",
            data_source="PARTICLE_SUMMARY",
            severity="INFO",
            logical_operator="AND",
            schedule_time="17:00",
            schedule_days="Mon,Tue,Wed,Thu,Fri,Sat",
            cooldown_minutes=720,
            template_id=t_sum.id if t_sum else None,
        )
        db.add(r3)
        db.flush()
        if g_qmm:
            db.add(models.RuleRecipientAssignment(rule_id=r3.id, recipient_type="TO", group_id=g_qmm.id))
        if g_mfc:
            db.add(models.RuleRecipientAssignment(rule_id=r3.id, recipient_type="TO", group_id=g_mfc.id))
        if g_mgmt:
            db.add(models.RuleRecipientAssignment(rule_id=r3.id, recipient_type="CC", group_id=g_mgmt.id))

        # Rule 4: Missing Daily WSA Analysis Update by Deadline
        r4 = models.AlertRule(
            name="Missing WSA Line 5 Analysis Update by 16:30 Deadline",
            description="Alerts when no Particle Summary analysis entry or 0 parts checked is recorded for today by 16:30.",
            is_enabled=True,
            priority=4,
            rule_category="SCHEDULED",
            trigger_type="MISSING_UPDATE_DEADLINE",
            data_source="PARTICLE_SUMMARY",
            severity="WARNING",
            logical_operator="AND",
            schedule_time="16:30",
            cooldown_minutes=720,
            template_id=t_gemba.id if t_gemba else None,
        )
        db.add(r4)
        db.flush()
        if g_qmm:
            db.add(models.RuleRecipientAssignment(rule_id=r4.id, recipient_type="TO", group_id=g_qmm.id))

        db.commit()

    # 4. Seed initial Excel snapshot as baseline so existing historical rows don't flood emails on first boot
    if db.query(models.DataRecordSnapshot).count() == 0:
        all_recs = service.collect_all_normalized_records()
        if all_recs:
            from backend.alerts.change_detector import detect_and_sync_changes
            detect_and_sync_changes(db, all_recs, seed_as_baseline_if_empty=True)
