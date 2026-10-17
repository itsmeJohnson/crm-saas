import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.organization import Organization
from app.models.user import User
from app.models.pipeline import Pipeline, PipelineStage
from app.models.assignment_config import AssignmentConfig
from app.core.security import get_password_hash
from app.core.config import settings

DATABASE_URL = str(settings.SQLALCHEMY_DATABASE_URI)

async def seed():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # 1. Organization
        stmt = select(Organization).filter(Organization.slug == "samartha-sankalpa")
        res = await session.execute(stmt)
        org = res.scalars().first()

        if not org:
            org = Organization(
                name="Samartha Sankalpa",
                slug="samartha-sankalpa",
                is_active=True,
                industry="telecalling",
                business_template="telecalling",
                timezone="Asia/Kolkata",
                currency="INR",
                language="English",
                country="India",
                country_code="IN",
                subscription_plan="Enterprise",
                subscription_status="active",
                max_users=50
            )
            session.add(org)
            await session.flush()
            print(f"Created Organization: {org.name} ({org.id})")
        else:
            print(f"Organization exists: {org.name} ({org.id})")

        # 2. Pipeline & Stages
        pipe_stmt = select(Pipeline).filter(Pipeline.organization_id == org.id, Pipeline.is_default == True)
        pipe = (await session.execute(pipe_stmt)).scalars().first()
        if not pipe:
            pipe = Pipeline(
                organization_id=org.id,
                name="Telecalling Sales Pipeline",
                description="Default outreach pipeline for Samartha Sankalpa telecalling campaigns",
                is_default=True,
                is_active=True
            )
            session.add(pipe)
            await session.flush()

            stages = [
                ("Fresh Leads", 1, True),
                ("Contacted / RNR", 2, False),
                ("Follow-up Scheduled", 3, False),
                ("Interested / Candidate Shortlisted", 4, False),
                ("Converted / Enrolled", 5, False),
                ("Dropped / Not Interested", 6, False)
            ]
            for name, pos, is_default in stages:
                stage = PipelineStage(
                    organization_id=org.id,
                    pipeline_id=pipe.id,
                    name=name,
                    order_position=pos,
                    is_system_default=is_default
                )
                session.add(stage)
            await session.flush()
            print("Created default Pipeline & Stages for Samartha Sankalpa")

        # 3. Assignment Config
        asgn_stmt = select(AssignmentConfig).filter(AssignmentConfig.organization_id == org.id)
        asgn = (await session.execute(asgn_stmt)).scalars().first()
        if not asgn:
            asgn = AssignmentConfig(
                organization_id=org.id,
                is_active=True,
                last_assigned_user_id=None
            )
            session.add(asgn)
            await session.flush()
            print("Created AssignmentConfig (is_active=True)")

        # 4. Users
        hashed_pwd = get_password_hash("Password@123")

        # John A - TeamLeader
        stmt_a = select(User).filter(User.email == "johnsondev02@gmail.com")
        user_a = (await session.execute(stmt_a)).scalars().first()
        if not user_a:
            user_a = User(
                organization_id=org.id,
                email="johnsondev02@gmail.com",
                first_name="John",
                last_name="A",
                role="TeamLeader",
                hashed_password=hashed_pwd,
                is_active=True,
                is_verified=True,
                phone="9876543210"
            )
            session.add(user_a)
            await session.flush()
            print(f"Created TeamLeader: John A ({user_a.email}) - ID: {user_a.id}")
        else:
            user_a.organization_id = org.id
            user_a.role = "TeamLeader"
            user_a.first_name = "John"
            user_a.last_name = "A"
            user_a.is_active = True
            await session.flush()
            print(f"Updated TeamLeader: John A ({user_a.email})")

        # John B - Telecaller (Employee)
        stmt_b = select(User).filter(User.email == "johnsonsoftwares8@gmail.com")
        user_b = (await session.execute(stmt_b)).scalars().first()
        if not user_b:
            user_b = User(
                organization_id=org.id,
                email="johnsonsoftwares8@gmail.com",
                first_name="John",
                last_name="B",
                role="Employee",
                reporting_to_id=user_a.id,
                hashed_password=hashed_pwd,
                is_active=True,
                is_verified=True,
                phone="9876543211"
            )
            session.add(user_b)
            await session.flush()
            print(f"Created Telecaller: John B ({user_b.email}) - ID: {user_b.id}")
        else:
            user_b.organization_id = org.id
            user_b.role = "Employee"
            user_b.first_name = "John"
            user_b.last_name = "B"
            user_b.reporting_to_id = user_a.id
            user_b.is_active = True
            await session.flush()
            print(f"Updated Telecaller: John B ({user_b.email})")

        # John C - Telecaller (Employee)
        stmt_c = select(User).filter(User.email == "contact@johnsonsoftwares.com")
        user_c = (await session.execute(stmt_c)).scalars().first()
        if not user_c:
            user_c = User(
                organization_id=org.id,
                email="contact@johnsonsoftwares.com",
                first_name="John",
                last_name="C",
                role="Employee",
                reporting_to_id=user_a.id,
                hashed_password=hashed_pwd,
                is_active=True,
                is_verified=True,
                phone="9876543212"
            )
            session.add(user_c)
            await session.flush()
            print(f"Created Telecaller: John C ({user_c.email}) - ID: {user_c.id}")
        else:
            user_c.organization_id = org.id
            user_c.role = "Employee"
            user_c.first_name = "John"
            user_c.last_name = "C"
            user_c.reporting_to_id = user_a.id
            user_c.is_active = True
            await session.flush()
            print(f"Updated Telecaller: John C ({user_c.email})")

        await session.commit()
        print("Successfully provisioned Samartha Sankalpa tenant, pipeline, and team members!")

if __name__ == "__main__":
    asyncio.run(seed())
