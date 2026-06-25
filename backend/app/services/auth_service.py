from datetime import datetime, timedelta, timezone
from typing import Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.repositories.session import UserSessionRepository
from app.schemas.auth import RegisterTenantRequest, Token, LoginRequest
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.models.user import User
from app.models.organization import Organization
from app.core.config import settings

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.user_repo = UserRepository(db)
        self.session_repo = UserSessionRepository(db)

    async def register_tenant(self, request: RegisterTenantRequest) -> Tuple[User, Organization]:
        # Check slug exists
        existing_org = await self.org_repo.get_by_slug(request.slug)
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Organization slug already in use"
            )

        # Check email exists
        existing_user = await self.user_repo.get_by_email(request.admin_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )

        # Validate constraints
        if request.licensed_seats < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum initial purchase is 10 Licensed Seats."
            )
        if request.contract_months < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum initial contract is 3 months."
            )

        # Create organization
        org = await self.org_repo.create({
            "name": request.company_name,
            "slug": request.slug
        })

        # Create owner user
        hashed_password = get_password_hash(request.admin_password)
        user = await self.user_repo.create({
            "organization_id": org.id,
            "email": request.admin_email,
            "hashed_password": hashed_password,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "role": "OrgAdmin",
            "is_verified": True
        })

        # Set up subscription
        import uuid
        from sqlalchemy import select
        from app.models.plan import Plan
        from app.models.tenant_subscription import TenantSubscription
        from app.models.invoice import Invoice
        from app.models.invoice_config import InvoiceConfig
        from app.models.commercial_settings import CommercialSettings
        from app.models.seat_history import SeatAssignmentHistory
        from app.models.payment import Payment

        # Fetch Starter plan
        plan_stmt = select(Plan).where(Plan.name == "Starter")
        plan_res = await self.db.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if not plan:
            # Fallback to any plan if Starter is not seeded
            plan_stmt = select(Plan)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()
            if not plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No subscription plans found. Please seed plans first."
                )

        now_utc = datetime.now(timezone.utc)
        sub_end = now_utc + timedelta(days=request.contract_months * 30)
        
        # 1. Create TenantSubscription
        sub = TenantSubscription(
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
            start_date=now_utc,
            end_date=sub_end,
            auto_renew=True,
            billing_cycle="monthly",
            users_purchased=request.licensed_seats,
            users_active=1
        )
        self.db.add(sub)
        await self.db.flush()

        # 2. Update Organization denormalized fields
        org.subscription_plan = plan.name
        org.max_users = request.licensed_seats
        org.subscription_expires_at = sub_end.replace(tzinfo=None)
        org.subscription_status = "active"
        self.db.add(org)

        # 3. Assign Seat to the newly created admin user
        user.seat_number = "Seat-001"
        self.db.add(user)

        history = SeatAssignmentHistory(
            organization_id=org.id,
            seat_number="Seat-001",
            user_id=user.id,
            action="Assigned",
            performed_by_id=user.id,
            remarks="Initial admin seat assignment"
        )
        self.db.add(history)

        # 4. Generate initial paid Invoice
        comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
        comm_res = await self.db.execute(comm_stmt)
        comm_settings = comm_res.scalar_one_or_none()
        if not comm_settings:
            comm_settings = CommercialSettings(id="default")
            self.db.add(comm_settings)
            await self.db.flush()

        config_stmt = select(InvoiceConfig).where(InvoiceConfig.id == "default")
        config_res = await self.db.execute(config_stmt)
        invoice_config = config_res.scalar_one_or_none()
        if not invoice_config:
            invoice_config = InvoiceConfig(id="default")
            self.db.add(invoice_config)
            await self.db.flush()

        prefix = invoice_config.invoice_prefix or "INV"
        currency = invoice_config.currency or comm_settings.default_currency or "INR"
        invoice_num = f"{prefix}-REG-{uuid.uuid4().hex[:8].upper()}-{int(now_utc.timestamp())}"

        price_per_seat = float(plan.monthly_price if plan.monthly_price > 0 else plan.price_inr)
        base_amount = price_per_seat * request.licensed_seats
        
        gst_rate = float(comm_settings.default_gst)
        if comm_settings.gst_inclusive:
            gst_amount = base_amount * (gst_rate / (100.0 + gst_rate))
            taxable_amount = base_amount - gst_amount
            total_amount = base_amount
        else:
            taxable_amount = base_amount
            gst_amount = taxable_amount * (gst_rate / 100.0)
            total_amount = taxable_amount + gst_amount

        invoice = Invoice(
            organization_id=org.id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Paid",
            due_date=now_utc + timedelta(days=comm_settings.grace_period_days),
            plan_name=plan.name,
            amount_inr=total_amount if currency == "INR" else 0.0,
            currency=currency,
            issue_date=now_utc,
            payment_status="paid",
            subscription_id=sub.id,
            setup_charges=0.0,
            extra_users_amount=0.0,
            discount_amount=0.0,
            gst_amount=gst_amount,
            total_amount=total_amount
        )
        self.db.add(invoice)
        await self.db.flush()

        # 5. Create Payment record
        payment = Payment(
            invoice_id=invoice.id,
            payment_reference=f"REF-REG-{uuid.uuid4().hex[:8].upper()}",
            gateway="UPI",
            status="Paid",
            transaction_id=f"TXN-REG-{uuid.uuid4().hex[:12].upper()}",
            paid_date=now_utc,
            remarks="Initial registration payment"
        )
        self.db.add(payment)
        await self.db.flush()

        return user, org

    async def authenticate_user(self, request: LoginRequest) -> User:
        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User account is deactivated"
            )
        return user

    async def create_user_session(self, user_id: Any, ip_address: str | None = None, user_agent: str | None = None) -> Token:
        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.session_repo.create({
            "user_id": user_id,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent
        })
        
        return Token(access_token=access_token, refresh_token=refresh_token)

    async def refresh_session(self, refresh_token: str, ip_address: str | None = None, user_agent: str | None = None) -> Token:
        session = await self.session_repo.get_by_refresh_token(refresh_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        # Rotate tokens: revoke current session
        await self.session_repo.revoke_session(session.id)
        
        # Check if the user is active
        user = await self.user_repo.get(session.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User account is inactive or not found"
            )

        # Create new tokens and new session
        return await self.create_user_session(session.user_id, ip_address, user_agent)

    async def logout_session(self, refresh_token: str) -> None:
        session = await self.session_repo.get_by_refresh_token(refresh_token)
        if session:
            await self.session_repo.revoke_session(session.id)
