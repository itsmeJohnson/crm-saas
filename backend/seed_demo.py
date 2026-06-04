import asyncio
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.note import Note
from app.models.session import UserSession
from app.models.invitation import UserInvitation
from app.models.audit_log import AuditLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_demo")

async def seed():
    async with async_session_maker() as session:
        logger.info("Initializing database session...")
        
        # 1. Clean up existing 'democorp' data to support re-seeding
        org_result = await session.execute(select(Organization).filter(Organization.slug == "democorp"))
        existing_org = org_result.scalars().first()
        
        if existing_org:
            logger.info("Found existing Demo Corp organization. Cleaning up old demo records...")
            org_id = existing_org.id
            
            # Delete dependent entities manually
            await session.execute(delete(Note).filter(Note.organization_id == org_id))
            await session.execute(delete(Activity).filter(Activity.organization_id == org_id))
            await session.execute(delete(Lead).filter(Lead.organization_id == org_id))
            await session.execute(delete(Contact).filter(Contact.organization_id == org_id))
            await session.execute(delete(Company).filter(Company.organization_id == org_id))
            
            user_ids_result = await session.execute(select(User.id).filter(User.organization_id == org_id))
            user_ids = user_ids_result.scalars().all()
            logger.info(f"Deleting sessions for user IDs: {user_ids}")
            if user_ids:
                del_sess_res = await session.execute(delete(UserSession).filter(UserSession.user_id.in_(user_ids)))
                logger.info(f"Deleted {del_sess_res.rowcount} user sessions.")
                
            await session.execute(delete(UserInvitation).filter(UserInvitation.organization_id == org_id))
            await session.execute(delete(AuditLog).filter(AuditLog.organization_id == org_id))
            await session.execute(delete(User).filter(User.organization_id == org_id))
            await session.execute(delete(Organization).filter(Organization.id == org_id))
            await session.commit()
            logger.info("Cleanup completed successfully.")

        # 2. Create Organization
        org = Organization(
            name="Demo Corp",
            slug="democorp",
            is_active=True
        )
        session.add(org)
        await session.flush()
        logger.info(f"Created organization: {org.name} (id: {org.id})")

        # 3. Create Users with hashed passwords ('password123')
        pwd_hash = get_password_hash("password123")
        
        users = [
            User(
                organization_id=org.id,
                email="demo_admin@democorp.com",
                hashed_password=pwd_hash,
                first_name="Alice",
                last_name="Admin",
                role="OrgAdmin",
                is_active=True,
                is_verified=True
            ),
            User(
                organization_id=org.id,
                email="demo_mgr@democorp.com",
                hashed_password=pwd_hash,
                first_name="Bob",
                last_name="Manager",
                role="Manager",
                is_active=True,
                is_verified=True
            ),
            User(
                organization_id=org.id,
                email="demo_emp@democorp.com",
                hashed_password=pwd_hash,
                first_name="Charlie",
                last_name="Employee",
                role="Employee",
                is_active=True,
                is_verified=True
            )
        ]
        session.add_all(users)
        await session.flush()
        
        admin_user, mgr_user, emp_user = users
        logger.info("Created demo users: Alice (Admin), Bob (Manager), Charlie (Employee).")

        # 4. Create Companies
        companies_data = [
            ("Acme Corp", "Software", "acme.com"),
            ("Globex Corp", "Manufacturing", "globex.com"),
            ("Initech", "Consulting", "initech.com"),
            ("Umbrella Corp", "Biotech", "umbrella.com"),
            ("Hooli", "Internet Services", "hooli.xyz"),
            ("Soylent Corp", "Food & Beverage", "soylent.com"),
            ("Wayne Enterprises", "Aerospace & Defense", "waynecorp.com"),
            ("Stark Industries", "Energy & Technology", "starkindustries.com"),
            ("Tyrell Corp", "Artificial Intelligence", "tyrell.io"),
            ("Cyberdyne Systems", "Robotics", "cyberdyne.ai")
        ]
        
        companies = []
        for name, industry, domain in companies_data:
            comp = Company(
                organization_id=org.id,
                name=name,
                industry=industry,
                domain=domain,
                website=f"https://www.{domain}",
                phone="555-0199",
                assigned_user_id=mgr_user.id if "Acme" in name or "Stark" in name else emp_user.id,
                created_by=admin_user.id
            )
            session.add(comp)
            companies.append(comp)
        await session.flush()
        logger.info(f"Seeded {len(companies)} companies.")

        # 5. Create Contacts
        contacts_data = [
            ("John", "Smith", "j.smith@acme.com", companies[0]), # Acme
            ("Jane", "Miller", "j.miller@acme.com", companies[0]),
            ("Arthur", "Pendleton", "arthur@globex.com", companies[1]), # Globex
            ("Peter", "Gibbons", "peter@initech.com", companies[2]), # Initech
            ("Samir", "Nagheenanajar", "samir@initech.com", companies[2]),
            ("Alice", "Marcus", "a.marcus@umbrella.com", companies[3]), # Umbrella
            ("Richard", "Hendricks", "richard@hooli.xyz", companies[4]), # Hooli
            ("Nelson", "Bighetti", "bighead@hooli.xyz", companies[4]),
            ("Robert", "Soylent", "robert@soylent.com", companies[5]), # Soylent
            ("Bruce", "Wayne", "bwayne@waynecorp.com", companies[6]), # Wayne
            ("Lucius", "Fox", "lfox@waynecorp.com", companies[6]),
            ("Pepper", "Potts", "ppotts@starkindustries.com", companies[7]), # Stark
            ("Happy", "Hogan", "happy@starkindustries.com", companies[7]),
            ("Rachael", "Replicant", "rachael@tyrell.io", companies[8]), # Tyrell
            ("Eldon", "Tyrell", "etyrell@tyrell.io", companies[8]),
            ("Sarah", "Connor", "sconnor@cyberdyne.ai", companies[9]), # Cyberdyne
            ("John", "Connor", "jconnor@cyberdyne.ai", companies[9]),
            ("Miles", "Dyson", "mdyson@cyberdyne.ai", companies[9])
        ]
        
        contacts = []
        for first, last, email, comp in contacts_data:
            contact = Contact(
                organization_id=org.id,
                first_name=first,
                last_name=last,
                email=email,
                phone="555-0120",
                company_id=comp.id,
                assigned_user_id=comp.assigned_user_id,
                created_by=admin_user.id
            )
            session.add(contact)
            contacts.append(contact)
        await session.flush()
        logger.info(f"Seeded {len(contacts)} contacts.")

        # 6. Create Leads
        leads_data = [
            ("Acme Enterprise Deal", "Qualified", 150000.0, companies[0], contacts[0], mgr_user),
            ("Wayne Tech Licensing", "New", 85000.0, companies[6], contacts[9], emp_user),
            ("Stark Arc Reactor RFP", "Nurturing", 250000.0, companies[7], contacts[11], mgr_user),
            ("Hooli Search Ads Account", "Contacted", 45000.0, companies[4], contacts[6], emp_user),
            ("Globex Logistics Contract", "New", 60000.0, companies[1], contacts[2], emp_user),
            ("Umbrella Pharma Research", "Qualified", 120000.0, companies[3], contacts[5], mgr_user),
            ("Cyberdyne Core Expansion", "Nurturing", 95000.0, companies[9], contacts[15], emp_user),
            ("Tyrell Nexus-9 roll-out", "Qualified", 180000.0, companies[8], contacts[13], mgr_user),
            ("Initech System Upgrade", "Lost", 25000.0, companies[2], contacts[3], emp_user),
            ("Soylent Green Logistics", "Contacted", 15000.0, companies[5], contacts[8], emp_user),
        ]

        leads = []
        for title, status, value, comp, contact, assignee in leads_data:
            lead = Lead(
                organization_id=org.id,
                first_name=contact.first_name,
                last_name=contact.last_name,
                email=contact.email,
                phone=contact.phone,
                company_name=comp.name,
                title=title,
                status=status,
                source="Direct Pitch" if value > 100000 else "Website Request",
                value=value,
                assigned_user_id=assignee.id,
                created_by=admin_user.id
            )
            session.add(lead)
            leads.append((lead, comp, contact, assignee))
        await session.flush()
        logger.info(f"Seeded {len(leads)} leads.")

        # 7. Create Activities & Notes
        logger.info("Logging interactive activities and notes history...")
        for lead, comp, contact, assignee in leads:
            # Add a completed activity
            activity_completed = Activity(
                organization_id=org.id,
                activity_type="Call",
                subject="Introductory discovery call",
                description=f"Completed introductory discovery call with {contact.first_name}. Discussed their budget for the {lead.title} opportunity.",
                due_date=datetime.now(timezone.utc) - timedelta(days=2),
                status="Completed",
                assigned_user_id=assignee.id,
                lead_id=lead.id,
                contact_id=contact.id,
                company_id=comp.id,
                created_by=admin_user.id
            )
            session.add(activity_completed)

            # Add a planned future activity
            activity_planned = Activity(
                organization_id=org.id,
                activity_type="Meeting" if lead.value > 100000 else "Task",
                subject="Follow-up proposal sync" if lead.value > 100000 else "Send collateral",
                description=f"Scheduled proposal discussion and project overview sync for {lead.title}.",
                due_date=datetime.now(timezone.utc) + timedelta(days=4),
                status="Planned",
                assigned_user_id=assignee.id,
                lead_id=lead.id,
                contact_id=contact.id,
                company_id=comp.id,
                created_by=admin_user.id
            )
            session.add(activity_planned)

            # Add a note
            note = Note(
                organization_id=org.id,
                content=f"Initial discovery completed. Customer expressed high interest. Estimated deal close value at ${lead.value:,.2f}.",
                lead_id=lead.id,
                contact_id=contact.id,
                company_id=comp.id,
                created_by=assignee.id
            )
            session.add(note)

        await session.commit()
        logger.info("Database seeding successfully completed!")

if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)
