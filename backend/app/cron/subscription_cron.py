import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_subscription import TenantSubscription
from app.models.organization import Organization
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

async def get_org_admin_email(db: AsyncSession, organization_id) -> str | None:
    """Helper to fetch the email of the OrgAdmin for the organization."""
    stmt = select(User.email).where(
        User.organization_id == organization_id,
        User.role == "OrgAdmin",
        User.is_deleted == False
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()

async def process_subscription_transitions(db: AsyncSession, reference_date: datetime) -> int:
    """
    Evaluates and applies state transitions for all active/trial/expired tenant subscriptions.
    Returns the count of transitioned records.
    """
    logger.info("Starting subscription state transitions evaluation for date: %s", reference_date)
    
    # Load CommercialSettings
    from app.models.commercial_settings import CommercialSettings
    comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
    comm_res = await db.execute(comm_stmt)
    comm_settings = comm_res.scalar_one_or_none()
    if not comm_settings:
        comm_settings = CommercialSettings(id="default")
        db.add(comm_settings)
        await db.flush()

    stmt = (
        select(TenantSubscription)
        .options(selectinload(TenantSubscription.plan))
        .where(TenantSubscription.is_deleted == False)
    )
    res = await db.execute(stmt)
    subscriptions = res.scalars().all()
    
    transition_count = 0
    service = SubscriptionService(db)

    for sub in subscriptions:
        org_stmt = select(Organization).where(Organization.id == sub.organization_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if not org or org.is_deleted:
            continue

        admin_email = await get_org_admin_email(db, sub.organization_id)
        if not admin_email:
            logger.warning("No OrgAdmin user found for tenant %s. Skipping notification.", org.name)
            # We still transition the subscription but email won't be sent.
        
        # 1. TRIAL transitions
        if sub.status == "trial":
            if sub.trial_end_date and sub.trial_end_date <= reference_date:
                # Trial ended -> transition to expired
                sub.status = "expired"
                org.subscription_status = "expired"
                transition_count += 1
                
                if admin_email:
                    subject = "Your Free Trial Has Ended"
                    custom_body = None
                    if comm_settings.trial_expiry_template:
                        custom_body = comm_settings.trial_expiry_template.replace("{customer_name}", org.name).replace("{days_left}", "0")
                    send_email(
                        to_email=admin_email,
                        subject=subject,
                        template_name="trial_ended.html",
                        context={
                            "org_name": org.name,
                            "upgrade_url": "/subscription",
                            "custom_body": custom_body
                        }
                    )
            elif sub.trial_end_date and (sub.trial_end_date - reference_date) <= timedelta(days=comm_settings.trial_reminder_days):
                # Alert trial ending soon
                if sub.trial_end_date > reference_date:
                    days_left = (sub.trial_end_date - reference_date).days + 1
                    if admin_email:
                        subject = "Your Free Trial is Ending Soon"
                        custom_body = None
                        if comm_settings.trial_expiry_template:
                            custom_body = comm_settings.trial_expiry_template.replace("{customer_name}", org.name).replace("{days_left}", str(days_left))
                        send_email(
                            to_email=admin_email,
                            subject=subject,
                            template_name="trial_ending_soon.html",
                            context={
                                "org_name": org.name,
                                "days_left": days_left,
                                "trial_end_date": sub.trial_end_date.strftime("%B %d, %Y"),
                                "upgrade_url": "/subscription",
                                "custom_body": custom_body
                            }
                        )

        # 2. ACTIVE / EXPIRING_SOON transitions
        elif sub.status in ["active", "expiring_soon"]:
            if sub.end_date <= reference_date:
                # Expired subscription
                if sub.auto_renew:
                    try:
                        # Attempt mocked automatic renewal
                        await service.renew_subscription(sub.organization_id)
                        logger.info("Subscription for tenant %s automatically renewed.", org.name)
                        transition_count += 1
                    except Exception as e:
                        logger.error("Auto-renewal failed for tenant %s: %s", org.name, e)
                        sub.status = "expired"
                        org.subscription_status = "expired"
                        transition_count += 1
                        if admin_email:
                            subject = "Your Subscription Has Expired"
                            custom_body = None
                            if comm_settings.payment_failed_template:
                                custom_body = comm_settings.payment_failed_template.replace("{customer_name}", org.name).replace("{invoice_number}", "Auto-Renew")
                            send_email(
                                to_email=admin_email,
                                subject=subject,
                                template_name="plan_expired.html",
                                context={
                                    "org_name": org.name,
                                    "renew_url": "/subscription",
                                    "custom_body": custom_body
                                }
                            )
                else:
                    sub.status = "expired"
                    org.subscription_status = "expired"
                    transition_count += 1
                    if admin_email:
                        subject = "Your Subscription Has Expired"
                        custom_body = None
                        send_email(
                            to_email=admin_email,
                            subject=subject,
                            template_name="plan_expired.html",
                            context={
                                "org_name": org.name,
                                "renew_url": "/subscription",
                                "custom_body": custom_body
                              }
                        )
            elif (sub.end_date - reference_date) <= timedelta(days=3):
                # Transition status to expiring_soon if it was active
                if sub.status == "active":
                    sub.status = "expiring_soon"
                    org.subscription_status = "expiring_soon"
                    transition_count += 1
                    
                if admin_email:
                    subject = "Subscription Renewal Reminder"
                    custom_body = None
                    if comm_settings.renewal_reminder_template:
                        custom_body = comm_settings.renewal_reminder_template.replace("{customer_name}", org.name).replace("{renewal_date}", sub.end_date.strftime("%B %d, %Y"))
                    send_email(
                        to_email=admin_email,
                        subject=subject,
                        template_name="renewal_reminder.html",
                        context={
                            "org_name": org.name,
                            "plan_name": sub.plan.name if sub.plan else org.subscription_plan,
                            "renewal_date": sub.end_date.strftime("%B %d, %Y"),
                            "amount": str(sub.plan.price_inr) if (sub.plan) else "0.00",
                            "custom_body": custom_body
                        }
                    )

        # 3. EXPIRED transitions -> SUSPENDED
        elif sub.status == "expired":
            # Grace period is loaded dynamically from CommercialSettings
            if (reference_date - sub.end_date) >= timedelta(days=comm_settings.grace_period_days):
                sub.status = "suspended"
                org.subscription_status = "suspended"
                transition_count += 1
                
                if admin_email:
                    send_email(
                        to_email=admin_email,
                        subject="Your Account Has Been Suspended",
                        template_name="account_suspended.html",
                        context={
                            "org_name": org.name,
                            "support_email": "support@telecrm-saas.com"
                        }
                    )

    if transition_count > 0:
        await db.commit()
        logger.info("Completed subscription transitions: updated %d records.", transition_count)
        
    return transition_count

async def run_daily_subscription_check(db_session_maker) -> None:
    """Entry point invoked by the background scheduler."""
    logger.info("Executing daily midnight subscription checks...")
    async with db_session_maker() as db:
        try:
            now = datetime.now(timezone.utc)
            await process_subscription_transitions(db, now)
        except Exception as e:
            logger.error("Error running daily subscription check: %s", e)
            await db.rollback()
