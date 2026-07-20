"""Approval Automation cron.

Applies chain timeout actions (escalate / auto-approve / auto-reject) to
requests stuck at a level longer than their chain's timeout_hours. The legacy
on-demand escalate-overdue endpoint is separate and untouched.
"""
import logging
from sqlalchemy import select

from app.models.approval import ApprovalChain
from app.services.approval_service import ApprovalService

logger = logging.getLogger("app.cron.approval")


async def run_approval_timeouts(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(ApprovalChain.organization_id).filter(
            ApprovalChain.is_active == True, ApprovalChain.is_deleted == False,
            ApprovalChain.timeout_hours.isnot(None),
            ApprovalChain.timeout_action.isnot(None)).distinct())).scalars().all())
    totals = {"processed": 0, "auto_approved": 0, "auto_rejected": 0, "escalated": 0}
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await ApprovalService(db).process_timeouts(org_id)
                await db.commit()
                for k in totals:
                    totals[k] += out.get(k, 0)
        except Exception as e:
            logger.error("Approval timeout scan for org %s failed: %s", org_id, e)
    if totals["processed"]:
        logger.info("Approval timeouts: %s across %d org(s).", totals, len(org_ids))
