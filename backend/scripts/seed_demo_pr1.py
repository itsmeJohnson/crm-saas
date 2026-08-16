"""PR-1 demo-data seeder — additive, idempotent.

Populates the EXISTING Professional Demo Co. org with a realistic sales
lifecycle so every dashboard, report, funnel and reminder has data to show:
org hierarchy (director → managers → executives) across Sales/Collections/
Support departments, 1000 leads spread across the pipeline, call activities,
follow-ups (Activity + reminder-bearing Task), and calendar meetings/site-visits.

Re-running is safe: it detects the sentinel director and exits without
duplicating. Run:  docker exec crm-backend python scripts/seed_demo_pr1.py
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.department import Department
from app.models.calendar_event import CalendarEvent
from app.models.pipeline import PipelineStage

ORG_ID = uuid.UUID("11b09ef1-fb33-450d-ab24-847e63d3af1c")
SENTINEL_EMAIL = "director@abcprops-demo.com"
PW = get_password_hash("Password123!")
rnd = random.Random(4242)  # deterministic

FIRST = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Ananya", "Diya", "Isha", "Kavya",
         "Rohan", "Kabir", "Advait", "Sai", "Krish", "Priya", "Neha", "Pooja", "Sneha", "Riya",
         "Karan", "Nikhil", "Rahul", "Amit", "Vikram", "Meera", "Anjali", "Divya", "Simran", "Tara"]
LAST = ["Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Menon", "Gupta", "Singh", "Mehta",
        "Joshi", "Rao", "Desai", "Kapoor", "Malhotra", "Chopra", "Bose", "Das", "Pillai", "Shetty"]
CITIES = ["Mumbai", "Pune", "Bengaluru", "Hyderabad", "Chennai", "Delhi", "Gurgaon", "Noida", "Ahmedabad", "Kochi"]
SOURCES = ["Website", "Referral", "Facebook Ads", "Google Ads", "Walk-in", "IVR", "Property Portal", "Cold Call"]
PROJECTS = ["Skyline Residency", "Green Valley Villas", "Lake View Apartments", "Metro Heights",
            "Palm Grove", "Sunrise Enclave", "Harmony Towers", "Orchard Square"]

# stage name -> (lead.status, weight, is_won, is_lost)
STAGE_PLAN = [
    ("New Lead",   "New",         0.34, False, False),
    ("Contacted",  "Contacted",   0.20, False, False),
    ("Interested", "Interested",  0.18, False, False),
    ("Negotiation","Negotiation", 0.10, False, False),
    ("Won",        "Won",         0.11, True,  False),
    ("Lost",       "Lost",        0.07, False, True),
]
DISPOSITIONS = ["Picked", "RNR", "Busy", "Switch Off", "Interested", "Not Interested"]


def name():
    return rnd.choice(FIRST), rnd.choice(LAST)


def phone():
    return "+91" + str(rnd.randint(6, 9)) + "".join(str(rnd.randint(0, 9)) for _ in range(9))


async def main():
    async with async_session_maker() as db:
        # idempotency guard
        exists = (await db.execute(select(User.id).filter(User.email == SENTINEL_EMAIL))).scalar()
        if exists:
            print("Already seeded (sentinel director present). Nothing to do.")
            return

        admin = (await db.execute(select(User).filter(
            User.organization_id == ORG_ID, User.role == "OrgAdmin",
            User.is_active == True, User.is_deleted == False))).scalars().first()
        if not admin:
            print("No OrgAdmin found for the demo org; aborting.")
            return

        stages = {s.name: s.id for s in (await db.execute(select(PipelineStage).filter(
            PipelineStage.organization_id == ORG_ID, PipelineStage.is_deleted == False))).scalars().all()}
        missing = [n for (n, *_ ) in STAGE_PLAN if n not in stages]
        if missing:
            print(f"Missing pipeline stages {missing}; aborting.")
            return

        now = datetime.now(timezone.utc)

        # ---- Departments ----
        depts = {}
        for dn, code in [("Sales", "SAL"), ("Collections", "COL"), ("Support", "SUP")]:
            d = Department(organization_id=ORG_ID, name=dn, code=code, status="active", created_by=admin.id)
            db.add(d); depts[dn] = d
        await db.flush()

        # ---- People: 1 director, 3 managers, 20 execs, +2 collections, +1 support ----
        def mk_user(first, last, role, reports_to, dept, email):
            u = User(organization_id=ORG_ID, email=email, hashed_password=PW,
                     first_name=first, last_name=last, role=role, is_active=True, is_verified=True,
                     reporting_to_id=reports_to, department_id=dept.id if dept else None, phone=phone())
            db.add(u); return u

        director = mk_user("Rajiv", "Khanna", "Manager", admin.id, depts["Sales"], SENTINEL_EMAIL)
        await db.flush()
        depts["Sales"].head_user_id = director.id

        managers = [mk_user(*name(), "Manager", director.id, depts["Sales"], f"sales.manager{i}@abcprops-demo.com")
                    for i in range(1, 4)]
        await db.flush()

        execs = []
        for i in range(1, 21):
            mgr = managers[(i - 1) % 3]
            execs.append(mk_user(*name(), "Employee", mgr.id, depts["Sales"], f"sales.exec{i}@abcprops-demo.com"))
        # collections + support personas (mapped roles)
        coll = [mk_user(*name(), "Employee", managers[0].id, depts["Collections"], f"collections{i}@abcprops-demo.com") for i in (1, 2)]
        supp = [mk_user(*name(), "Employee", managers[0].id, depts["Support"], f"support1@abcprops-demo.com")]
        await db.flush()

        exec_ids = [e.id for e in execs]

        # ---- Leads across the pipeline ----
        N = 1000
        weights = [w for (_, _, w, *_ ) in STAGE_PLAN]
        stage_choices = rnd.choices(range(len(STAGE_PLAN)), weights=weights, k=N)
        leads = []
        for idx in range(N):
            sname, lstatus, _w, is_won, is_lost = STAGE_PLAN[stage_choices[idx]]
            f, l = name()
            created = now - timedelta(days=rnd.randint(0, 120), hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59))
            owner = rnd.choice(exec_ids)
            val = rnd.choice([500000, 1500000, 2500000, 4000000, 7500000, 12000000, 25000000])
            lead = Lead(
                organization_id=ORG_ID, first_name=f, last_name=l, phone=phone(),
                email=f"{f.lower()}.{l.lower()}{idx}@example.com", city=rnd.choice(CITIES),
                company_name=None, title=f"{rnd.choice(PROJECTS)} enquiry", status=lstatus,
                source=rnd.choice(SOURCES), value=val, priority=rnd.choice(["Low", "Medium", "Medium", "High", "Urgent"]),
                score=rnd.randint(10, 95), assigned_user_id=owner, created_by=director.id,
                stage_id=stages[sname], call_attempts_count=rnd.randint(0, 5),
            )
            lead.created_at = created
            if is_won:
                lead.converted_at = created + timedelta(days=rnd.randint(1, 20))
            if is_lost:
                lead.lost_reason = rnd.choice(["Budget", "Bought elsewhere", "Not serious", "Location mismatch"])
            leads.append(lead)
            db.add(lead)
        await db.flush()

        # ---- Call activities (some dated today so "Today's Calls" shows) ----
        act_count = 0
        for lead in leads:
            for _ in range(rnd.randint(1, 3)):
                today = rnd.random() < 0.18
                when = now - (timedelta(hours=rnd.randint(0, 8)) if today
                              else timedelta(days=rnd.randint(1, 90), hours=rnd.randint(0, 12)))
                a = Activity(organization_id=ORG_ID, activity_type="Call",
                             subject=f"Call: {lead.first_name} {lead.last_name}",
                             description="Outbound call", status="Completed",
                             assigned_user_id=lead.assigned_user_id, created_by=lead.assigned_user_id,
                             lead_id=lead.id, call_direction="OUTBOUND",
                             call_disposition=rnd.choice(DISPOSITIONS), call_duration=rnd.randint(20, 400))
                a.created_at = when
                db.add(a); act_count += 1
        await db.flush()

        # ---- Follow-ups: Activity(Follow-up) + reminder-bearing Task, due today/tomorrow/overdue ----
        fu_leads = rnd.sample(leads, 300)
        buckets = ([("today", 0)] * 100) + ([("tomorrow", 1)] * 80) + ([("overdue", -1)] * 120)
        rnd.shuffle(buckets)
        fu_count = 0
        for lead, (_label, offset) in zip(fu_leads, buckets):
            if offset == -1:
                due = now - timedelta(days=rnd.randint(1, 6), hours=rnd.randint(0, 6))
            elif offset == 0:
                due = now + timedelta(hours=rnd.randint(1, 8))
            else:
                due = now + timedelta(days=1, hours=rnd.randint(0, 8))
            db.add(Activity(organization_id=ORG_ID, activity_type="Follow-up",
                            subject=f"Follow-up (call) — {lead.status}", description="Scheduled follow-up",
                            due_date=due, status="Planned", assigned_user_id=lead.assigned_user_id,
                            created_by=lead.assigned_user_id, lead_id=lead.id, call_disposition="Follow-up"))
            db.add(Task(organization_id=ORG_ID, title=f"Follow up: {lead.title}",
                        description=f"Follow up with {lead.first_name}", priority=lead.priority,
                        status="Todo", due_date=due, remind_at=due - timedelta(minutes=30),
                        assigned_user_id=lead.assigned_user_id, created_by=lead.assigned_user_id, lead_id=lead.id))
            fu_count += 1
        await db.flush()

        # ---- Calendar: 150 meetings + 80 site visits ----
        cal_count = 0
        for kind, count in [("Meeting", 150), ("Site Visit", 80)]:
            for lead in rnd.sample(leads, count):
                start = now + timedelta(days=rnd.randint(-10, 14), hours=rnd.randint(9, 18))
                db.add(CalendarEvent(organization_id=ORG_ID, title=f"{kind}: {lead.title}",
                                     event_type="Meeting", start_at=start, end_at=start + timedelta(hours=1),
                                     status="Scheduled", assigned_user_id=lead.assigned_user_id,
                                     created_by=lead.assigned_user_id, lead_id=lead.id,
                                     remind_at=start - timedelta(minutes=30)))
                cal_count += 1

        await db.commit()
        print(f"Seeded: 1 director, {len(managers)} managers, {len(execs)} execs, "
              f"{len(coll)} collections, {len(supp)} support | 3 departments")
        print(f"Leads: {len(leads)} | Call activities: {act_count} | Follow-ups(+tasks): {fu_count} | Calendar: {cal_count}")


asyncio.run(main())
