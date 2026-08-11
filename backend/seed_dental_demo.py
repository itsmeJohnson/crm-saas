"""
SmileCare Dental Clinic - Specialized Demo Data Seeder
Populates comprehensive, end-to-end Dental Clinic CRM data for the primary tenant
and/or dedicated SmileCare Dental Clinic organization.

Covers full lifecycle:
Marketing -> Leads -> Follow-up -> Appointments -> Patients -> Treatments -> Billing -> Recall
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone, date

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.company import Company
from app.models.calendar_event import CalendarEvent
from app.models.customer_order import CustomerOrder
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.task import Task
from app.models.activity import Activity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_dental_demo")

PATIENT_FIRST_NAMES = [
    "Aarav", "Aditi", "Advait", "Akash", "Ananya", "Anushka", "Aryan", "Ayush",
    "Bhavya", "Chetan", "Dev", "Diya", "Gauri", "Harsh", "Isha", "Ishaan",
    "Karan", "Kavya", "Khushi", "Kunal", "Manish", "Meera", "Mihir", "Naveen",
    "Neha", "Nikhil", "Pooja", "Pranav", "Priya", "Rahul", "Rhea", "Rishi",
    "Rohan", "Sakshi", "Sameer", "Sanika", "Sanya", "Shlok", "Shreya", "Siddharth",
    "Sneha", "Tanvi", "Tarun", "Varun", "Vedika", "Vihaan", "Yash", "Zara",
    "Amit", "Deepak", "Kiran", "Madhu", "Nandini", "Preeti", "Rajesh", "Sunita"
]

PATIENT_LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Deshmukh", "Kulkarni", "Iyer", "Nair",
    "Reddy", "Rao", "Joshi", "Gupta", "Agarwal", "Bansal", "Kapoor", "Malhotra",
    "Chopra", "Singhal", "Bhatia", "Saxena", "Pandey", "Mishra", "Trivedi", "Shah",
    "Parekh", "Merchant", "D'Souza", "Fernandes", "Menon", "Pillai", "Shetty", "Hegde"
]

TREATMENTS_CATALOG = [
    {"name": "Root Canal Therapy (RCT)", "category": "Endodontics", "price": 12000, "steps": ["Access Cavity & Cleaning", "Biomechanical Prep", "Obturation (Filling)", "Crown Placement"]},
    {"name": "Titanium Dental Implant", "category": "Implantology", "price": 45000, "steps": ["Surgical Implant Placement", "Osseointegration & Healing", "Abutment Placement", "Permanent Crown Fitting"]},
    {"name": "Invisalign / Clear Aligners", "category": "Orthodontics", "price": 95000, "steps": ["3D Digital Scan & Plan", "Tray Set 1-10 Dispensed", "Mid-treatment Review", "Tray Set 11-20 Dispensed", "Refinement & Retainers"]},
    {"name": "Ceramic Braces Treatment", "category": "Orthodontics", "price": 60000, "steps": ["Bracket Bonding", "Initial Alignment Wire", "Space Closure & Leveling", "Detailing & Debonding"]},
    {"name": "Zirconia Crown & Bridge", "category": "Prosthodontics", "price": 15000, "steps": ["Tooth Preparation & Impression", "Temporary Crown", "Final Crown Cementation"]},
    {"name": "Laser Teeth Whitening", "category": "Cosmetic", "price": 9500, "steps": ["Scaling & Polishing", "Gingival Barrier Application", "Laser Light Activation (3 cycles)", "Fluoride & Post-care"]},
    {"name": "Deep Ultrasonic Cleaning & Polishing", "category": "Preventive", "price": 2500, "steps": ["Supragingival Scaling", "Subgingival Debridement", "Prophy-jet Polishing", "Oral Hygiene Instruction"]},
    {"name": "Wisdom Tooth Surgical Extraction", "category": "Oral Surgery", "price": 8500, "steps": ["OPG X-Ray Evaluation", "Surgical Disimpaction", "Suturing & Hemostasis", "Suture Removal & Review"]},
    {"name": "Composite Tooth-Colored Filling", "category": "Restorative", "price": 3000, "steps": ["Caries Excavation", "Etching & Bonding", "Layered Composite Placement", "Polishing & Occlusal Check"]},
    {"name": "Comprehensive Dental Consultation & OPG", "category": "Diagnostics", "price": 1000, "steps": ["Intraoral Camera Examination", "Digital OPG X-Ray", "Treatment Plan Presentation"]}
]

LEAD_SOURCES = ["Google Ads", "Instagram", "Website", "WhatsApp", "Referral", "Walk-in", "Google Search"]

async def seed_dental_demo():
    async with async_session_maker() as db:
        logger.info("Starting Dental Clinic Demo Data Seeding...")
        
        # 1. Identify primary tenant organizations to seed
        stmt = select(Organization).where(Organization.id == uuid.UUID("00a0698b-b367-4a95-8126-c8aa7096db0b"))
        primary_org = (await db.execute(stmt)).scalar_one_or_none()
        
        if primary_org:
            primary_org.name = "SmileCare Dental Clinic"
            primary_org.slug = "smilecare-dental"
            primary_org.currency = "INR"
            primary_org.timezone = "Asia/Kolkata"
            target_orgs = [primary_org]
        else:
            stmt_alt = select(Organization).where(Organization.slug == "smilecare-dental")
            primary_org = (await db.execute(stmt_alt)).scalar_one_or_none()
            if not primary_org:
                primary_org = Organization(
                    id=uuid.uuid4(),
                    name="SmileCare Dental Clinic",
                    slug="smilecare-dental",
                    currency="INR",
                    timezone="Asia/Kolkata",
                    is_active=True,
                    subscription_plan="Professional",
                    subscription_status="active"
                )
                db.add(primary_org)
                await db.flush()
            target_orgs = [primary_org]

        for org in target_orgs:
            org_id = org.id
            logger.info(f"Populating dental clinic data for organization: {org.name} ({org_id})")

            # 2. Doctors & Staff Users
            users_to_create = [
                {
                    "email": "dr.arvind@smilecaredental.com",
                    "first_name": "Dr. Arvind",
                    "last_name": "Mehta",
                    "role": "OrgAdmin",
                    "phone": "+91 9820112233"
                },
                {
                    "email": "dr.priya@smilecaredental.com",
                    "first_name": "Dr. Priya",
                    "last_name": "Sharma",
                    "role": "Manager",
                    "phone": "+91 9820223344"
                },
                {
                    "email": "dr.vikram@smilecaredental.com",
                    "first_name": "Dr. Vikram",
                    "last_name": "Rao",
                    "role": "Employee",
                    "phone": "+91 9820334455"
                },
                {
                    "email": "sneha.reception@smilecaredental.com",
                    "first_name": "Sneha",
                    "last_name": "Patel",
                    "role": "Employee",
                    "phone": "+91 9820445566"
                },
                {
                    "email": "ananya.manager@smilecaredental.com",
                    "first_name": "Ananya",
                    "last_name": "Verma",
                    "role": "Manager",
                    "phone": "+91 9820556677"
                }
            ]

            created_users = []
            for udata in users_to_create:
                u_stmt = select(User).where(User.email == udata["email"], User.organization_id == org_id)
                u = (await db.execute(u_stmt)).scalar_one_or_none()
                if not u:
                    u = User(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        email=udata["email"],
                        first_name=udata["first_name"],
                        last_name=udata["last_name"],
                        role=udata["role"],
                        phone=udata["phone"],
                        hashed_password=get_password_hash("Demo@12345"),
                        is_active=True,
                        is_verified=True
                    )
                    db.add(u)
                    await db.flush()
                created_users.append(u)

            j_stmt = select(User).where(User.email == "johnsondev02@gmail.com")
            j_user = (await db.execute(j_stmt)).scalar_one_or_none()
            if j_user:
                j_user.first_name = "Dr. Johnson"
                j_user.last_name = "Dev"
                j_user.role = "OrgAdmin"
                j_user.organization_id = org_id
                created_users.append(j_user)

            doctors = [u for u in created_users if "dr." in u.email.lower() or u.email == "johnsondev02@gmail.com" or "Dr." in (u.first_name or "")]
            if not doctors:
                doctors = created_users[:3]
            staff_members = [u for u in created_users if u not in doctors]
            if not staff_members:
                staff_members = created_users

            # 3. Dental Pipeline & Stages
            pipe_stmt = select(Pipeline).where(Pipeline.organization_id == org_id, Pipeline.name == "Dental Patient Journey")
            pipeline = (await db.execute(pipe_stmt)).scalar_one_or_none()
            if not pipeline:
                # An org must have exactly one default pipeline. Clear any existing
                # default (e.g. the base "Software Pipeline") before making the
                # dental journey the default, so we never end up with two defaults.
                from sqlalchemy import update as _sa_update
                await db.execute(
                    _sa_update(Pipeline)
                    .where(Pipeline.organization_id == org_id, Pipeline.is_default == True)
                    .values(is_default=False)
                )
                pipeline = Pipeline(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    name="Dental Patient Journey",
                    is_default=True
                )
                db.add(pipeline)
                await db.flush()

                dental_stages = [
                    ("New Enquiry", 10, False, False),
                    ("Contacted / Consultation Booked", 30, False, False),
                    ("Consultation Completed", 50, False, False),
                    ("Treatment Proposed", 70, False, False),
                    ("Follow-up / Scheduling", 80, False, False),
                    ("Treatment Started", 90, False, False),
                    ("Treatment Completed / Converted", 100, True, False),
                    ("Lost / Not Interested", 0, False, True),
                ]
                stage_objects = []
                for idx, (s_name, prob, is_won, is_lost) in enumerate(dental_stages):
                    stg = PipelineStage(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        pipeline_id=pipeline.id,
                        name=s_name,
                        order_position=idx + 1,
                        probability=prob,
                        is_won=is_won,
                        is_lost=is_lost
                    )
                    db.add(stg)
                    stage_objects.append(stg)
                await db.flush()
            else:
                stg_stmt = select(PipelineStage).where(PipelineStage.pipeline_id == pipeline.id).order_by(PipelineStage.order_position)
                stage_objects = list((await db.execute(stg_stmt)).scalars().all())

            # 4. Default Dental Company / Clinic Account
            comp_stmt = select(Company).where(Company.organization_id == org_id, Company.name == "SmileCare In-Clinic Patients")
            clinic_comp = (await db.execute(comp_stmt)).scalar_one_or_none()
            if not clinic_comp:
                clinic_comp = Company(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    name="SmileCare In-Clinic Patients",
                    industry="Healthcare",
                    company_type="Customer",
                    created_by=created_users[0].id
                )
                db.add(clinic_comp)
                await db.flush()

            # 5. Dental Patients (Contacts)
            existing_contacts_stmt = select(Contact).where(Contact.organization_id == org_id)
            existing_contacts = list((await db.execute(existing_contacts_stmt)).scalars().all())

            patients = list(existing_contacts)
            now = datetime.now(timezone.utc)

            patient_categories = [
                "Active Treatment", "New Patient", "Returning Patient", 
                "Treatment Completed", "Recall Due", "Follow-up Due"
            ]

            needed_patients = max(0, 120 - len(patients))
            for i in range(needed_patients):
                fn = random.choice(PATIENT_FIRST_NAMES)
                ln = random.choice(PATIENT_LAST_NAMES)
                age = random.randint(18, 68)
                gender = random.choice(["Male", "Female", "Other"])
                cat = random.choices(patient_categories, weights=[30, 20, 20, 15, 10, 5])[0]
                assigned_doc = random.choice(doctors)
                chosen_treatment = random.choice(TREATMENTS_CATALOG)

                last_visit = now - timedelta(days=random.randint(2, 240))
                next_appt = now + timedelta(days=random.randint(1, 45)) if cat in ["Active Treatment", "New Patient", "Recall Due"] else None

                tags = [cat, chosen_treatment["category"], chosen_treatment["name"]]
                custom_fields = {
                    "age": age,
                    "gender": gender,
                    "blood_group": random.choice(["O+", "A+", "B+", "AB+", "O-", "B-"]),
                    "allergies": random.choice(["None", "Penicillin", "Latex", "Local Anesthetic", "None", "None"]),
                    "medical_conditions": random.choice(["None", "Diabetes", "Hypertension", "Thyroid", "None", "None"]),
                    "current_treatment": chosen_treatment["name"],
                    "primary_doctor": f"{assigned_doc.first_name} {assigned_doc.last_name}",
                    "patient_category": cat,
                    "last_visit_date": last_visit.strftime("%Y-%m-%d"),
                    "next_appointment_date": next_appt.strftime("%Y-%m-%d") if next_appt else None,
                    "outstanding_balance": random.choice([0, 0, 1500, 4000, 8000, 15000, 25000]) if cat in ["Active Treatment", "Follow-up Due"] else 0,
                    "dental_notes": f"Patient presented with interest in {chosen_treatment['name']}. Good oral hygiene."
                }

                contact = Contact(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    company_id=clinic_comp.id,
                    first_name=fn,
                    last_name=ln,
                    email=f"{fn.lower()}.{ln.lower()}{random.randint(10, 99)}@gmail.com",
                    phone=f"+91 98{random.randint(10000000, 99999999)}",
                    job_title=f"Patient (#{1000 + i})",
                    assigned_user_id=assigned_doc.id,
                    created_by=created_users[0].id,
                    tags=tags,
                    custom_fields=custom_fields
                )
                db.add(contact)
                patients.append(contact)
            
            await db.flush()

            # 6. Dental Leads
            existing_leads_stmt = select(Lead).where(Lead.organization_id == org_id)
            existing_leads = list((await db.execute(existing_leads_stmt)).scalars().all())

            needed_leads = max(0, 50 - len(existing_leads))
            for i in range(needed_leads):
                fn = random.choice(PATIENT_FIRST_NAMES)
                ln = random.choice(PATIENT_LAST_NAMES)
                source = random.choice(LEAD_SOURCES)
                chosen_treatment = random.choice(TREATMENTS_CATALOG)
                stage = random.choice(stage_objects)
                assigned_doc = random.choice(doctors)
                priority = random.choices(["Low", "Medium", "High", "Urgent"], weights=[15, 45, 30, 10])[0]

                created_dt = now - timedelta(days=random.randint(0, 25), hours=random.randint(0, 23))

                lead = Lead(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    first_name=fn,
                    last_name=ln,
                    title=f"{chosen_treatment['name']} - {fn} {ln}",
                    email=f"{fn.lower()}.{ln.lower()}{random.randint(100, 999)}@gmail.com",
                    phone=f"+91 97{random.randint(10000000, 99999999)}",
                    city=random.choice(["Mumbai", "Bangalore", "Pune", "Delhi", "Hyderabad", "Chennai"]),
                    source=source,
                    value=chosen_treatment["price"],
                    priority=priority,
                    status=stage.name,
                    stage_id=stage.id,
                    pipeline_id=pipeline.id,
                    assigned_user_id=assigned_doc.id,
                    created_by=staff_members[0].id,
                    created_at=created_dt,
                    custom_fields={
                        "interested_treatment": chosen_treatment["name"],
                        "treatment_category": chosen_treatment["category"],
                        "preferred_doctor": f"{assigned_doc.first_name} {assigned_doc.last_name}",
                        "consultation_date": (now + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d") if "Consultation" in stage.name else None,
                        "lead_notes": f"Enquired via {source} for {chosen_treatment['name']}. Requested evening slot."
                    }
                )
                db.add(lead)

            await db.flush()

            # 7. Today's Appointments & Scheduled Calendar Events
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
            
            slots_today = [
                ("09:00", "09:45", "Dental Consultation & Digital X-Ray", "Completed", "Paid"),
                ("09:45", "10:30", "Root Canal Therapy (Step 2 - Cleaning)", "Completed", "Partially Paid"),
                ("10:30", "11:15", "Ceramic Braces Adjustment & Wire Change", "Completed", "Paid"),
                ("11:15", "12:00", "Laser Teeth Whitening Session", "In Treatment", "Paid"),
                ("12:00", "12:45", "Titanium Dental Implant Consultation", "Arrived", "Pending"),
                ("14:00", "14:45", "Zirconia Crown Fitting & Cementation", "Confirmed", "Paid"),
                ("14:45", "15:30", "Deep Ultrasonic Cleaning & Polishing", "Confirmed", "Pending"),
                ("15:30", "16:15", "Wisdom Tooth Surgical Extraction Review", "Booked", "Pending"),
                ("16:15", "17:00", "Invisalign First Tray Dispensing", "Booked", "Pending"),
                ("17:00", "17:45", "Composite Aesthetic Filling (Upper Molar)", "Booked", "Pending"),
                ("18:00", "18:30", "Emergency Toothache Consultation", "Booked", "Pending"),
                ("18:30", "19:00", "Post-Op Follow-up & Suture Check", "Booked", "Paid"),
            ]

            for slot_idx, (t_start, t_end, t_name, status_appt, pay_status) in enumerate(slots_today):
                start_h, start_m = map(int, t_start.split(":"))
                end_h, end_m = map(int, t_end.split(":"))
                
                s_dt = today_start.replace(hour=start_h, minute=start_m)
                e_dt = today_start.replace(hour=end_h, minute=end_m)
                
                patient = patients[slot_idx % len(patients)]
                doc = doctors[slot_idx % len(doctors)]

                appt_event = CalendarEvent(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    title=f"{t_name} - {patient.first_name} {patient.last_name}",
                    description=f"Treatment: {t_name}\nDoctor: {doc.first_name} {doc.last_name}\nStatus: {status_appt}\nPayment: {pay_status}",
                    event_type="Appointment",
                    location=f"Operatory #{(slot_idx % 3) + 1}, SmileCare Dental",
                    start_at=s_dt,
                    end_at=e_dt,
                    status=status_appt,
                    assigned_user_id=doc.id,
                    created_by=staff_members[0].id,
                    contact_id=patient.id,
                    attendees=[{"name": f"{patient.first_name} {patient.last_name}", "phone": patient.phone, "doctor": f"{doc.first_name} {doc.last_name}"}]
                )
                db.add(appt_event)

            for day_offset in range(1, 14):
                day_base = today_start + timedelta(days=day_offset)
                for hour in [10, 11, 14, 16, 17]:
                    patient = patients[(day_offset * 5 + hour) % len(patients)]
                    doc = doctors[(day_offset + hour) % len(doctors)]
                    trt = random.choice(TREATMENTS_CATALOG)

                    future_appt = CalendarEvent(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        title=f"{trt['name']} - {patient.first_name} {patient.last_name}",
                        description=f"Procedure: {trt['name']}\nDoctor: {doc.first_name} {doc.last_name}",
                        event_type="Appointment",
                        location=f"Operatory #{random.randint(1, 3)}, SmileCare Dental",
                        start_at=day_base.replace(hour=hour, minute=0),
                        end_at=day_base.replace(hour=hour, minute=45),
                        status="Confirmed" if day_offset <= 3 else "Scheduled",
                        assigned_user_id=doc.id,
                        created_by=staff_members[0].id,
                        contact_id=patient.id
                    )
                    db.add(future_appt)

            await db.flush()

            # 8. Active Treatments (Customer Orders & Treatment Plans)
            for p_idx, patient in enumerate(patients[:35]):
                trt = TREATMENTS_CATALOG[p_idx % len(TREATMENTS_CATALOG)]
                doc = doctors[p_idx % len(doctors)]
                
                total_val = float(trt["price"])
                paid_val = random.choice([total_val, total_val * 0.6, total_val * 0.5, 0.0])
                paid_val = round(paid_val, 2)

                steps_total = len(trt["steps"])
                step_curr = random.randint(1, steps_total)
                step_name = trt["steps"][step_curr - 1]

                order = CustomerOrder(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    company_id=clinic_comp.id,
                    contact_id=patient.id,
                    order_number=f"TRT-2026-{1000 + p_idx}",
                    status="Fulfilled" if paid_val == total_val and step_curr == steps_total else "Confirmed",
                    currency="INR",
                    order_date=now - timedelta(days=random.randint(2, 45)),
                    items=[{
                        "description": trt["name"],
                        "category": trt["category"],
                        "doctor": f"{doc.first_name} {doc.last_name}",
                        "current_step": f"Step {step_curr} of {steps_total}: {step_name}",
                        "progress_percent": int((step_curr / steps_total) * 100),
                        "quantity": 1,
                        "unit_price": total_val,
                        "amount": total_val
                    }],
                    subtotal=total_val,
                    tax_amount=0,
                    discount_amount=0,
                    total_amount=total_val,
                    notes=f"Clinical protocol for {patient.first_name} {patient.last_name}. Primary dentist: {doc.first_name} {doc.last_name}.",
                    created_by=doc.id
                )
                db.add(order)
                await db.flush()

                # 9. Invoices & Payments for this Treatment
                inv_status = "Paid" if paid_val >= total_val else ("PartiallyPaid" if paid_val > 0 else "Sent")
                invoice = CustomerInvoice(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    company_id=clinic_comp.id,
                    contact_id=patient.id,
                    order_id=order.id,
                    invoice_number=f"INV-SMILE-{2000 + p_idx}",
                    status=inv_status,
                    currency="INR",
                    issue_date=order.order_date,
                    due_date=now + timedelta(days=15),
                    items=order.items,
                    subtotal=total_val,
                    total_amount=total_val,
                    amount_paid=paid_val,
                    notes=f"Invoice for {trt['name']}",
                    created_by=staff_members[0].id
                )
                db.add(invoice)
                await db.flush()

                if paid_val > 0:
                    payment = CustomerPayment(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        company_id=clinic_comp.id,
                        invoice_id=invoice.id,
                        amount=paid_val,
                        currency="INR",
                        method=random.choice(["UPI", "Card", "Cash", "BankTransfer"]),
                        reference=f"PAY-REF-{random.randint(100000, 999999)}",
                        paid_at=now - timedelta(days=random.randint(0, 10)),
                        notes=f"Received against {invoice.invoice_number}",
                        created_by=staff_members[0].id
                    )
                    db.add(payment)

            # 10. Follow-ups & Recalls (Tasks & Activities)
            followup_configs = [
                ("6-Month Routine Recall & Dental Checkup", "Recall", -2, "Overdue", "High"),
                ("Post-RCT Crown Sensitivity Review Call", "Post Treatment", 0, "Due Today", "High"),
                ("Invisalign Next Aligners Pick-up Follow-up", "Treatment", 0, "Due Today", "Medium"),
                ("Pending Treatment Plan Decision Follow-up", "Consultation", 1, "Upcoming", "Medium"),
                ("Implant Healing Suture Check Reminder", "Post Treatment", 2, "Upcoming", "High"),
                ("Outstanding Balance Payment Reminder Call", "Payment", -1, "Overdue", "Medium"),
                ("Teeth Whitening 1-Month Post-Care Review", "Recall", 3, "Upcoming", "Low"),
                ("New Lead Inquiry - Book Consultation Call", "New Lead", 0, "Due Today", "Urgent"),
                ("Wisdom Tooth Extraction 24hr Recovery Check", "Post Treatment", 0, "Due Today", "Urgent"),
                ("Pediatric Dental Checkup Recall Reminder", "Recall", -3, "Overdue", "Medium")
            ]

            for f_idx, (f_title, f_type, day_diff, f_status_label, priority) in enumerate(followup_configs * 3):
                patient = patients[f_idx % len(patients)]
                doc = doctors[f_idx % len(doctors)]
                due_dt = now + timedelta(days=day_diff)

                task = Task(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    title=f"[{f_type}] {f_title} - {patient.first_name} {patient.last_name}",
                    description=f"Patient: {patient.first_name} {patient.last_name} ({patient.phone})\nType: {f_type}\nAssigned: {doc.first_name} {doc.last_name}",
                    priority=priority,
                    status="Done" if day_diff < -5 else ("InProgress" if day_diff == 0 else "Todo"),
                    due_date=due_dt,
                    assigned_user_id=staff_members[0].id if "Call" in f_title or "Reminder" in f_title else doc.id,
                    created_by=created_users[0].id,
                    contact_id=patient.id,
                    checklist=[
                        {"id": "1", "text": "Review clinical notes", "done": day_diff < 0},
                        {"id": "2", "text": "Contact patient via WhatsApp / Call", "done": day_diff < -2},
                        {"id": "3", "text": "Schedule next appointment if requested", "done": False}
                    ]
                )
                db.add(task)

                act = Activity(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    activity_type="Call" if "Call" in f_title else ("WhatsApp" if "Reminder" in f_title else "Task"),
                    subject=f"Follow-up: {f_title}",
                    description=f"Follow-up regarding {patient.first_name}'s treatment plan and recovery status.",
                    due_date=due_dt,
                    status="Completed" if day_diff < 0 else "Planned",
                    assigned_user_id=doc.id,
                    contact_id=patient.id,
                    created_by=created_users[0].id,
                    call_duration=random.randint(45, 180) if "Call" in f_title else None,
                    call_disposition="Interested" if day_diff < 0 else None,
                    wa_status="delivered" if "Reminder" in f_title else None
                )
                db.add(act)

            await db.commit()
            logger.info("Successfully seeded all Dental Clinic demo data!")

if __name__ == "__main__":
    asyncio.run(seed_dental_demo())
