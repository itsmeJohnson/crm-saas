"""Approval Workflow service — a generic, multi-level approval engine.

One request type at a time (leave/expense/discount/quotation/target/user/role/
generic) flows through a configurable chain of levels. Each level names an
approver by role (Manager = the requester's reporting manager; OrgAdmin = any
org admin) or a specific user; an active delegation lets a delegate act for
them. Every action is recorded (history), the final decision notifies the
requester and fires the approval workflow, and overdue requests can be
escalated. Domain-specific flows (leave/attendance/template approvals) keep
their own rich paths — this is the org-wide unified surface.
"""
from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.approval import (
    ApprovalChain, ApprovalRequest, ApprovalAction, ApprovalDelegation, APPROVAL_TYPES,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services import rule_evaluator

ROLE_APPROVERS = ("Manager", "OrgAdmin", "SuperAdmin")
STEP_MODES = ("any", "all")  # "all" = parallel level: every eligible approver must approve
TIMEOUT_ACTIONS = ("escalate", "auto_approve", "auto_reject")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _is_manager(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _can_admin(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    def _require_admin(self, actor: User):
        if not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can manage approval chains.")

    # ================= Chains =================
    async def _get_chain(self, actor: User, chain_id: uuid.UUID) -> ApprovalChain:
        c = (await self.db.execute(select(ApprovalChain).filter(
            ApprovalChain.id == chain_id, ApprovalChain.organization_id == actor.organization_id,
            ApprovalChain.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval chain not found")
        return c

    def _validate_steps(self, steps: list) -> list:
        if not steps:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A chain needs at least one level.")
        out = []
        for i, s in enumerate(steps, start=1):
            role = s.get("approver_role")
            uid = s.get("approver_user_id")
            mode = s.get("mode") or "any"
            if not role and not uid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Level {i} needs an approver_role or approver_user_id.")
            if role and role not in ROLE_APPROVERS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"approver_role must be one of {list(ROLE_APPROVERS)}")
            if mode not in STEP_MODES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"step mode must be one of {list(STEP_MODES)}")
            out.append({"level": i, "approver_role": role, "approver_user_id": str(uid) if uid else None,
                        "mode": mode, "conditions": s.get("conditions") or None})
        return out

    def _validate_timeout(self, data: dict) -> None:
        ta = data.get("timeout_action")
        if ta and ta not in TIMEOUT_ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"timeout_action must be one of {list(TIMEOUT_ACTIONS)}")
        if ta and not data.get("timeout_hours"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="timeout_action needs timeout_hours.")

    async def create_chain(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        if data["request_type"] not in APPROVAL_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"request_type must be one of {list(APPROVAL_TYPES)}")
        steps = self._validate_steps(data["steps"])
        self._validate_timeout(data)
        c = ApprovalChain(organization_id=actor.organization_id, name=data["name"],
                          request_type=data["request_type"], min_amount=_d(data.get("min_amount", 0)),
                          steps=steps, escalation_hours=data.get("escalation_hours"),
                          conditions=data.get("conditions"),
                          auto_approve_conditions=data.get("auto_approve_conditions"),
                          auto_reject_conditions=data.get("auto_reject_conditions"),
                          timeout_hours=data.get("timeout_hours"), timeout_action=data.get("timeout_action"),
                          is_active=bool(data.get("is_active", True)), created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return self._serialize_chain(c)

    async def update_chain(self, actor: User, chain_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        c = await self._get_chain(actor, chain_id)
        if "steps" in data and data["steps"] is not None:
            c.steps = self._validate_steps(data["steps"])
        for f in ("name", "escalation_hours", "is_active", "conditions", "auto_approve_conditions",
                  "auto_reject_conditions", "timeout_hours", "timeout_action"):
            if f in data and data[f] is not None:
                setattr(c, f, data[f])
        self._validate_timeout({"timeout_action": c.timeout_action, "timeout_hours": c.timeout_hours})
        if "min_amount" in data and data["min_amount"] is not None:
            c.min_amount = _d(data["min_amount"])
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return self._serialize_chain(c)

    async def delete_chain(self, actor: User, chain_id: uuid.UUID) -> None:
        self._require_admin(actor)
        c = await self._get_chain(actor, chain_id)
        pending = (await self.db.execute(select(func.count(ApprovalRequest.id)).filter(
            ApprovalRequest.chain_id == c.id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending"))).scalar() or 0
        if pending:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{pending} pending request(s) use this chain. Resolve them first.")
        c.is_deleted = True
        self.db.add(c)
        await self.db.flush()

    async def list_chains(self, actor: User, request_type=None) -> list[dict]:
        q = select(ApprovalChain).filter(ApprovalChain.organization_id == actor.organization_id,
                                         ApprovalChain.is_deleted == False)
        if request_type:
            q = q.filter(ApprovalChain.request_type == request_type)
        rows = list((await self.db.execute(q.order_by(ApprovalChain.request_type.asc(),
                                                      ApprovalChain.min_amount.asc()))).scalars().all())
        return [self._serialize_chain(c) for c in rows]

    async def _resolve_chain(self, org_id, request_type: str, amount: float,
                             facts: dict | None = None) -> ApprovalChain | None:
        """Active chain for the type with the highest min_amount <= amount whose
        chain-level `conditions` rule tree (if any) matches the request facts —
        dynamic approval rules."""
        rows = list((await self.db.execute(select(ApprovalChain).filter(
            ApprovalChain.organization_id == org_id, ApprovalChain.is_deleted == False,
            ApprovalChain.is_active == True, ApprovalChain.request_type == request_type,
            ApprovalChain.min_amount <= _d(amount)).order_by(ApprovalChain.min_amount.desc()))).scalars().all())
        # at the same amount tier, a conditional (more specific) chain wins over a generic one
        rows.sort(key=lambda c: (-float(c.min_amount), 0 if c.conditions else 1))
        for c in rows:
            if not c.conditions or rule_evaluator.evaluate(c.conditions, facts or {}):
                return c
        return None

    @staticmethod
    def _request_facts(*, request_type: str, amount, title: str | None = None,
                       payload: dict | None = None, status_val: str = "pending",
                       current_level: int = 1) -> dict:
        facts = dict(payload) if isinstance(payload, dict) else {}
        facts.update({"request_type": request_type, "amount": float(amount or 0),
                      "title": title, "status": status_val, "current_level": current_level})
        return facts

    def _facts_for(self, req: ApprovalRequest) -> dict:
        return self._request_facts(request_type=req.request_type, amount=req.amount, title=req.title,
                                   payload=req.payload, status_val=req.status, current_level=req.current_level)

    def _next_active_level(self, chain: ApprovalChain | None, after_level: int, facts: dict) -> int | None:
        """The next chain level after `after_level` whose per-step conditions match
        (conditional approval — non-matching levels are skipped). None = no level
        left, the request is fully approved."""
        if not chain:
            return 1 if after_level < 1 else None
        for s in sorted(chain.steps, key=lambda x: x.get("level") or 0):
            lvl = s.get("level") or 0
            if lvl <= after_level:
                continue
            if not s.get("conditions") or rule_evaluator.evaluate(s.get("conditions"), facts):
                return lvl
        return None

    # ================= Requests =================
    async def create_request(self, actor: User, data: dict) -> dict:
        request_type = data["request_type"]
        if request_type not in APPROVAL_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"request_type must be one of {list(APPROVAL_TYPES)}")
        amount = float(data.get("amount") or 0)
        facts = self._request_facts(request_type=request_type, amount=amount, title=data["title"],
                                    payload=data.get("payload"))
        chain = await self._resolve_chain(actor.organization_id, request_type, amount, facts)
        total_levels = len(chain.steps) if chain else 1
        first_level = self._next_active_level(chain, 0, facts)
        req = ApprovalRequest(organization_id=actor.organization_id, request_type=request_type,
                              title=data["title"], description=data.get("description"),
                              amount=_d(data["amount"]) if data.get("amount") is not None else None,
                              reference_type=data.get("reference_type"), reference_id=data.get("reference_id"),
                              payload=data.get("payload"), chain_id=chain.id if chain else None,
                              current_level=first_level or 1, total_levels=total_levels, status="pending",
                              requested_by=actor.id, created_by=actor.id)
        self.db.add(req)
        await self.db.flush()
        await self.db.refresh(req)
        self.db.add(ApprovalAction(organization_id=actor.organization_id, request_id=req.id, level=0,
                                   actor_id=actor.id, action="submitted", note=data.get("description")))
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="APPROVAL_REQUESTED", resource_type="approval", resource_id=str(req.id),
                                   action_metadata={"type": request_type, "amount": amount})
        # auto-reject / auto-approve rules of the resolved chain decide on submit
        if chain and chain.auto_reject_conditions and rule_evaluator.evaluate(chain.auto_reject_conditions, facts):
            await self._decide(req, actor, approved=False, system_note="Auto-rejected by chain rules",
                               action_name="auto_rejected")
            return await self._serialize_request(req)
        if chain and chain.auto_approve_conditions and rule_evaluator.evaluate(chain.auto_approve_conditions, facts):
            await self._decide(req, actor, approved=True, system_note="Auto-approved by chain rules",
                               action_name="auto_approved")
            return await self._serialize_request(req)
        if chain and first_level is None:
            # every level's conditions skipped this request → nothing to approve
            await self._decide(req, actor, approved=True, system_note="All levels skipped by conditions",
                               action_name="auto_approved")
            return await self._serialize_request(req)
        await self._notify_level_approvers(req, chain)
        await self._run_workflow(req, actor, "approval_requested")
        return await self._serialize_request(req)

    async def _decide(self, req: ApprovalRequest, actor: User, *, approved: bool,
                      system_note: str | None = None, action_name: str | None = None) -> None:
        """Finalize a request (shared by manual, auto and timeout decisions)."""
        req.status = "approved" if approved else "rejected"
        req.decided_at = _now()
        self.db.add(req)
        if action_name:
            self.db.add(ApprovalAction(organization_id=req.organization_id, request_id=req.id,
                                       level=req.current_level, actor_id=None,
                                       action=action_name, note=system_note))
        await self.db.flush()
        await self._notify_requester(req, req.status)
        await self._run_workflow(req, actor, f"approval_{req.status}")

    async def _step_for_level(self, chain: ApprovalChain | None, level: int) -> dict | None:
        if not chain:
            return None
        for s in chain.steps:
            if s.get("level") == level:
                return s
        return None

    async def _eligible_approver_ids(self, req: ApprovalRequest, chain: ApprovalChain | None) -> set[uuid.UUID]:
        """Direct approvers for the request's current level (excludes delegates)."""
        step = await self._step_for_level(chain, req.current_level)
        ids: set[uuid.UUID] = set()
        if not step:
            # no chain configured → any OrgAdmin approves
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == req.organization_id, User.is_deleted == False,
                User.role.in_(["OrgAdmin", "SuperAdmin"])))).scalars().all()
            return set(rows)
        if step.get("approver_user_id"):
            ids.add(uuid.UUID(step["approver_user_id"]))
        elif step.get("approver_role") == "Manager":
            mgr = (await self.db.execute(select(User.reporting_to_id).filter(User.id == req.requested_by))).scalar()
            if mgr:
                ids.add(mgr)
        elif step.get("approver_role") in ("OrgAdmin", "SuperAdmin"):
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == req.organization_id, User.is_deleted == False,
                User.role == step["approver_role"]))).scalars().all()
            ids.update(rows)
        return ids

    async def _active_delegators_for(self, actor: User, request_type: str) -> set[uuid.UUID]:
        """Users who have delegated their approval authority to `actor` (active,
        covering this type and today)."""
        today = date.today()
        rows = list((await self.db.execute(select(ApprovalDelegation).filter(
            ApprovalDelegation.organization_id == actor.organization_id, ApprovalDelegation.is_deleted == False,
            ApprovalDelegation.is_active == True, ApprovalDelegation.delegate_id == actor.id,
            ApprovalDelegation.start_date <= today,
            or_(ApprovalDelegation.end_date.is_(None), ApprovalDelegation.end_date >= today),
            or_(ApprovalDelegation.request_type.is_(None), ApprovalDelegation.request_type == request_type)))).scalars().all())
        return {d.delegator_id for d in rows}

    async def _get_request(self, actor: User, request_id: uuid.UUID) -> ApprovalRequest:
        r = (await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.id == request_id, ApprovalRequest.organization_id == actor.organization_id,
            ApprovalRequest.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
        return r

    async def act(self, actor: User, request_id: uuid.UUID, approve: bool, note: str | None = None) -> dict:
        req = await self._get_request(actor, request_id)
        if req.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is already decided.")
        chain = None
        if req.chain_id:
            chain = (await self.db.execute(select(ApprovalChain).filter(ApprovalChain.id == req.chain_id))).scalars().first()
        eligible = await self._eligible_approver_ids(req, chain)
        on_behalf = None
        admin_override = False
        if actor.id not in eligible:
            # maybe the actor is a delegate for one of the eligible approvers
            delegators = await self._active_delegators_for(actor, req.request_type)
            match = eligible & delegators
            if match:
                on_behalf = next(iter(match))
            elif self._can_admin(actor):
                admin_override = True  # OrgAdmin can always act (and settles a parallel level)
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="You are not an approver for this request at its current level.")
        step = await self._step_for_level(chain, req.current_level)
        parallel = bool(step and (step.get("mode") or "any") == "all")
        if approve and parallel:
            already = await self._approved_ids_at_level(req)
            if (on_behalf or actor.id) in already:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="You have already approved this level.")
        self.db.add(ApprovalAction(organization_id=actor.organization_id, request_id=req.id, level=req.current_level,
                                   actor_id=actor.id, on_behalf_of=on_behalf,
                                   action="approved" if approve else "rejected", note=note))
        if not approve:
            await self._decide(req, actor, approved=False)  # any rejection vetoes the request
        else:
            level_done = True
            if parallel and not admin_override:
                await self.db.flush()
                approved_ids = await self._approved_ids_at_level(req)
                level_done = eligible.issubset(approved_ids)  # parallel: ALL eligible approvers must approve
            if not level_done:
                await self.db.flush()
            else:
                nxt = self._next_active_level(chain, req.current_level, self._facts_for(req))
                if nxt is not None:
                    req.current_level = nxt
                    self.db.add(req)
                    await self.db.flush()
                    await self._notify_level_approvers(req, chain)  # advance to next level (multi-level)
                else:
                    await self._decide(req, actor, approved=True)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action=f"APPROVAL_{'APPROVED' if approve else 'REJECTED'}",
                                   resource_type="approval", resource_id=str(req.id),
                                   action_metadata={"level": req.current_level, "on_behalf_of": str(on_behalf) if on_behalf else None})
        return await self._serialize_request(req)

    async def cancel(self, actor: User, request_id: uuid.UUID) -> dict:
        req = await self._get_request(actor, request_id)
        if req.requested_by != actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester or an admin can cancel.")
        if req.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending requests can be cancelled.")
        req.status = "cancelled"
        req.decided_at = _now()
        self.db.add(req)
        self.db.add(ApprovalAction(organization_id=actor.organization_id, request_id=req.id, level=req.current_level,
                                   actor_id=actor.id, action="cancelled", note=None))
        await self.db.flush()
        return await self._serialize_request(req)

    async def escalate_overdue(self, actor: User) -> dict:
        """Escalate pending requests older than their chain's escalation_hours:
        notify the next level's approvers (or org admins) and flag them. Safe to
        run repeatedly / from a scheduler."""
        self._require_admin(actor)
        now = _now()
        reqs = list((await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.organization_id == actor.organization_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending", ApprovalRequest.escalated == False))).scalars().all())
        escalated = 0
        for req in reqs:
            if not req.chain_id:
                continue
            chain = (await self.db.execute(select(ApprovalChain).filter(ApprovalChain.id == req.chain_id))).scalars().first()
            if not chain or not chain.escalation_hours:
                continue
            age_hours = (now - self._aware(req.created_at)).total_seconds() / 3600 if req.created_at else 0
            if age_hours < chain.escalation_hours:
                continue
            req.escalated = True
            self.db.add(req)
            self.db.add(ApprovalAction(organization_id=actor.organization_id, request_id=req.id,
                                       level=req.current_level, actor_id=actor.id, action="escalated",
                                       note=f"Pending > {chain.escalation_hours}h"))
            # notify org admins to intervene
            admins = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.is_deleted == False,
                User.role.in_(["OrgAdmin", "SuperAdmin"])))).scalars().all()
            for aid in admins:
                await self.notifier.create_notification(
                    organization_id=actor.organization_id, user_id=aid, category="approval",
                    title="Approval escalated", body=f'"{req.title}" has been pending too long.',
                    link_url="/approvals", priority="high", action_metadata={"request_id": str(req.id)})
            await self._run_workflow(req, actor, "approval_escalated")
            escalated += 1
        await self.db.flush()
        return {"escalated": escalated}

    async def _approved_ids_at_level(self, req: ApprovalRequest) -> set[uuid.UUID]:
        """Effective approvers (delegator when a delegate acted) who already
        approved the request's current level — drives parallel 'all' levels."""
        rows = list((await self.db.execute(select(ApprovalAction).filter(
            ApprovalAction.request_id == req.id, ApprovalAction.is_deleted == False,
            ApprovalAction.level == req.current_level, ApprovalAction.action == "approved"))).scalars().all())
        return {(a.on_behalf_of or a.actor_id) for a in rows if (a.on_behalf_of or a.actor_id)}

    async def process_timeouts(self, org_id: uuid.UUID) -> dict:
        """Apply each chain's timeout_action to pending requests stuck at a level
        longer than timeout_hours (measured from the last recorded action, so a
        multi-level request gets a fresh clock per level). Safe to run repeatedly
        — cron-driven and also exposed to admins on demand."""
        now = _now()
        reqs = list((await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.organization_id == org_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending", ApprovalRequest.chain_id.isnot(None)))).scalars().all())
        chains = {c.id: c for c in (await self.db.execute(select(ApprovalChain).filter(
            ApprovalChain.organization_id == org_id, ApprovalChain.is_deleted == False))).scalars().all()}
        out = {"processed": 0, "auto_approved": 0, "auto_rejected": 0, "escalated": 0}
        for req in reqs:
            chain = chains.get(req.chain_id)
            if not chain or not chain.timeout_hours or not chain.timeout_action:
                continue
            last_action_at = (await self.db.execute(select(func.max(ApprovalAction.created_at)).filter(
                ApprovalAction.request_id == req.id, ApprovalAction.is_deleted == False))).scalar()
            reference = last_action_at or req.created_at
            if not reference:
                continue
            elapsed_h = (now - self._aware(reference)).total_seconds() / 3600
            if elapsed_h < chain.timeout_hours:
                continue
            requester = (await self.db.execute(select(User).filter(User.id == req.requested_by))).scalars().first()
            note = f"Timed out after {chain.timeout_hours}h at level {req.current_level}"
            if chain.timeout_action == "auto_reject":
                await self._decide(req, requester, approved=False, system_note=note, action_name="auto_rejected")
                out["auto_rejected"] += 1
            elif chain.timeout_action == "auto_approve":
                # the timeout settles the whole level (incl. parallel), then advances
                self.db.add(ApprovalAction(organization_id=req.organization_id, request_id=req.id,
                                           level=req.current_level, actor_id=None, action="auto_approved", note=note))
                nxt = self._next_active_level(chain, req.current_level, self._facts_for(req))
                if nxt is not None:
                    req.current_level = nxt
                    self.db.add(req)
                    await self.db.flush()
                    await self._notify_level_approvers(req, chain)
                else:
                    await self._decide(req, requester, approved=True)
                out["auto_approved"] += 1
            else:  # escalate
                if req.escalated:
                    continue
                req.escalated = True
                self.db.add(req)
                self.db.add(ApprovalAction(organization_id=req.organization_id, request_id=req.id,
                                           level=req.current_level, actor_id=None, action="escalated", note=note))
                admins = (await self.db.execute(select(User.id).filter(
                    User.organization_id == org_id, User.is_deleted == False,
                    User.role.in_(["OrgAdmin", "SuperAdmin"])))).scalars().all()
                for aid in admins:
                    await self.notifier.create_notification(
                        organization_id=org_id, user_id=aid, category="approval",
                        title="Approval escalated", body=f'"{req.title}" timed out at level {req.current_level}.',
                        link_url="/approvals", priority="high", action_metadata={"request_id": str(req.id)})
                await self.db.flush()
                await self._run_workflow(req, requester, "approval_escalated")
                out["escalated"] += 1
            await self.audit.log_event(organization_id=org_id, actor_user_id=None,
                                       action="APPROVAL_TIMEOUT", resource_type="approval", resource_id=str(req.id),
                                       action_metadata={"action": chain.timeout_action, "hours": chain.timeout_hours})
            out["processed"] += 1
        await self.db.flush()
        return out

    async def process_timeouts_for(self, actor: User) -> dict:
        self._require_admin(actor)
        return await self.process_timeouts(actor.organization_id)

    # ================= Delegation =================
    async def create_delegation(self, actor: User, data: dict) -> dict:
        delegate_id = data["delegate_id"]
        if delegate_id == actor.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delegate to yourself.")
        u = (await self.db.execute(select(User.id).filter(
            User.id == delegate_id, User.organization_id == actor.organization_id, User.is_deleted == False))).scalar()
        if not u:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delegate not found in this org.")
        rt = data.get("request_type")
        if rt and rt not in APPROVAL_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"request_type must be one of {list(APPROVAL_TYPES)}")
        deleg = ApprovalDelegation(organization_id=actor.organization_id, delegator_id=actor.id,
                                   delegate_id=delegate_id, request_type=rt,
                                   start_date=data.get("start_date") or date.today(),
                                   end_date=data.get("end_date"), is_active=True, created_by=actor.id)
        self.db.add(deleg)
        await self.db.flush()
        await self.db.refresh(deleg)
        await self.notifier.create_notification(
            organization_id=actor.organization_id, user_id=delegate_id, category="approval",
            title="Approvals delegated to you",
            body=f"{await self._name(actor.id)} delegated their {rt or 'all'} approvals to you.",
            link_url="/approvals", action_metadata={"delegation_id": str(deleg.id)})
        return self._serialize_delegation(deleg)

    async def revoke_delegation(self, actor: User, delegation_id: uuid.UUID) -> dict:
        d = (await self.db.execute(select(ApprovalDelegation).filter(
            ApprovalDelegation.id == delegation_id, ApprovalDelegation.organization_id == actor.organization_id,
            ApprovalDelegation.is_deleted == False))).scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
        if d.delegator_id != actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the delegator or an admin can revoke.")
        d.is_active = False
        self.db.add(d)
        await self.db.flush()
        return self._serialize_delegation(d)

    async def list_delegations(self, actor: User) -> list[dict]:
        q = select(ApprovalDelegation).filter(ApprovalDelegation.organization_id == actor.organization_id,
                                              ApprovalDelegation.is_deleted == False)
        if not self._can_admin(actor):
            q = q.filter(or_(ApprovalDelegation.delegator_id == actor.id, ApprovalDelegation.delegate_id == actor.id))
        rows = list((await self.db.execute(q.order_by(ApprovalDelegation.created_at.desc()))).scalars().all())
        return [self._serialize_delegation(d) for d in rows]

    # ================= Queries / history / dashboard / reports =================
    async def list_requests(self, actor: User, *, box="mine", request_type=None, status_filter=None,
                            skip=0, limit=100) -> dict:
        q = select(ApprovalRequest).filter(ApprovalRequest.organization_id == actor.organization_id,
                                           ApprovalRequest.is_deleted == False)
        if box == "mine":
            q = q.filter(ApprovalRequest.requested_by == actor.id)
        elif box == "pending":
            # requests currently awaiting THIS actor's action
            pending_ids = await self._pending_for_actor(actor)
            if not pending_ids:
                return {"items": [], "total": 0}
            q = q.filter(ApprovalRequest.id.in_(list(pending_ids)))
        else:  # all — managers/admins see everything, others just their own
            if not self._is_manager(actor):
                q = q.filter(ApprovalRequest.requested_by == actor.id)
        if request_type:
            q = q.filter(ApprovalRequest.request_type == request_type)
        if status_filter:
            q = q.filter(ApprovalRequest.status == status_filter)
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(ApprovalRequest.created_at.desc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize_request(r) for r in rows], "total": total}

    async def _pending_for_actor(self, actor: User) -> set[uuid.UUID]:
        pend = list((await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.organization_id == actor.organization_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending"))).scalars().all())
        chains = {c.id: c for c in (await self.db.execute(select(ApprovalChain).filter(
            ApprovalChain.organization_id == actor.organization_id))).scalars().all()}
        out: set[uuid.UUID] = set()
        for req in pend:
            eligible = await self._eligible_approver_ids(req, chains.get(req.chain_id))
            if actor.id in eligible:
                out.add(req.id)
        # plus requests delegated to the actor
        for rt in APPROVAL_TYPES:
            delegators = await self._active_delegators_for(actor, rt)
            if not delegators:
                continue
            for req in pend:
                if req.request_type != rt or req.id in out:
                    continue
                eligible = await self._eligible_approver_ids(req, chains.get(req.chain_id))
                if eligible & delegators:
                    out.add(req.id)
        return out

    async def history(self, actor: User, request_id: uuid.UUID) -> list[dict]:
        req = await self._get_request(actor, request_id)
        rows = list((await self.db.execute(select(ApprovalAction).filter(
            ApprovalAction.request_id == req.id, ApprovalAction.is_deleted == False)
            .order_by(ApprovalAction.created_at.asc()))).scalars().all())
        names = await self._names({a.actor_id for a in rows} | {a.on_behalf_of for a in rows})
        return [{"id": str(a.id), "level": a.level, "action": a.action,
                 "actor_name": names.get(a.actor_id), "on_behalf_of_name": names.get(a.on_behalf_of) if a.on_behalf_of else None,
                 "note": a.note, "created_at": a.created_at.isoformat() if a.created_at else None} for a in rows]

    async def dashboard(self, actor: User) -> dict:
        my_pending = (await self.db.execute(select(func.count(ApprovalRequest.id)).filter(
            ApprovalRequest.organization_id == actor.organization_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.requested_by == actor.id, ApprovalRequest.status == "pending"))).scalar() or 0
        awaiting = len(await self._pending_for_actor(actor))
        by_status = dict((s, n) for s, n in (await self.db.execute(select(
            ApprovalRequest.status, func.count(ApprovalRequest.id)).filter(
            ApprovalRequest.organization_id == actor.organization_id, ApprovalRequest.is_deleted == False)
            .group_by(ApprovalRequest.status))).all())
        return {"my_pending": my_pending, "awaiting_my_action": awaiting,
                "total": sum(by_status.values()), "approved": by_status.get("approved", 0),
                "rejected": by_status.get("rejected", 0), "pending": by_status.get("pending", 0)}

    async def report(self, actor: User, request_type=None) -> dict:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers only.")
        q = select(ApprovalRequest).filter(ApprovalRequest.organization_id == actor.organization_id,
                                           ApprovalRequest.is_deleted == False)
        if request_type:
            q = q.filter(ApprovalRequest.request_type == request_type)
        reqs = list((await self.db.execute(q)).scalars().all())
        by_type: dict[str, dict] = {}
        for r in reqs:
            t = by_type.setdefault(r.request_type, {"total": 0, "approved": 0, "rejected": 0, "pending": 0,
                                                    "cancelled": 0, "_decide_secs": 0.0, "_decided": 0})
            t["total"] += 1
            t[r.status] = t.get(r.status, 0) + 1
            if r.decided_at and r.created_at:
                t["_decide_secs"] += (self._aware(r.decided_at) - self._aware(r.created_at)).total_seconds()
                t["_decided"] += 1
        rows = []
        for t, v in by_type.items():
            avg_h = round(v["_decide_secs"] / v["_decided"] / 3600, 1) if v["_decided"] else None
            rows.append({"request_type": t, "total": v["total"], "approved": v["approved"],
                         "rejected": v["rejected"], "pending": v["pending"], "cancelled": v.get("cancelled", 0),
                         "avg_decision_hours": avg_h})
        rows.sort(key=lambda x: -x["total"])
        return {"rows": rows}

    # ---------- notifications / workflow / helpers ----------
    async def _notify_level_approvers(self, req: ApprovalRequest, chain: ApprovalChain | None) -> None:
        approvers = await self._eligible_approver_ids(req, chain)
        for aid in approvers:
            if aid == req.requested_by:
                continue
            await self.notifier.create_notification(
                organization_id=req.organization_id, user_id=aid, category="approval",
                title="Approval needed",
                body=f'{req.request_type.title()} request "{req.title}" needs your approval (level {req.current_level}).',
                link_url="/approvals", priority="high", action_metadata={"request_id": str(req.id)})

    async def _notify_requester(self, req: ApprovalRequest, outcome: str) -> None:
        await self.notifier.create_notification(
            organization_id=req.organization_id, user_id=req.requested_by, category="approval",
            title=f"Request {outcome}", body=f'Your {req.request_type} request "{req.title}" was {outcome}.',
            link_url="/approvals", action_metadata={"request_id": str(req.id)})

    async def _run_workflow(self, req: ApprovalRequest, actor: User, trigger: str) -> None:
        from app.services.workflow_service import WorkflowService
        ent = _ApprovalEvent(req.organization_id, req.id, req.requested_by, req.request_type,
                             float(req.amount) if req.amount is not None else 0.0, req.status)
        await WorkflowService(self.db).run(trigger, ent, actor, entity_type="approval")

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    async def _name(self, user_id) -> str:
        return (await self._names({user_id})).get(user_id, "A teammate")

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    def _serialize_chain(self, c: ApprovalChain) -> dict:
        return {"id": str(c.id), "name": c.name, "request_type": c.request_type,
                "min_amount": float(c.min_amount), "steps": c.steps,
                "conditions": c.conditions, "auto_approve_conditions": c.auto_approve_conditions,
                "auto_reject_conditions": c.auto_reject_conditions,
                "timeout_hours": c.timeout_hours, "timeout_action": c.timeout_action,
                "escalation_hours": c.escalation_hours, "is_active": c.is_active, "created_at": c.created_at}

    def _serialize_delegation(self, d: ApprovalDelegation) -> dict:
        return {"id": str(d.id), "delegator_id": str(d.delegator_id), "delegate_id": str(d.delegate_id),
                "request_type": d.request_type, "start_date": d.start_date.isoformat(),
                "end_date": d.end_date.isoformat() if d.end_date else None, "is_active": d.is_active,
                "created_at": d.created_at}

    async def _serialize_request(self, r: ApprovalRequest) -> dict:
        names = await self._names({r.requested_by})
        return {"id": str(r.id), "request_type": r.request_type, "title": r.title, "description": r.description,
                "amount": float(r.amount) if r.amount is not None else None, "reference_type": r.reference_type,
                "reference_id": r.reference_id, "payload": r.payload, "current_level": r.current_level,
                "total_levels": r.total_levels, "status": r.status, "escalated": r.escalated,
                "requested_by": str(r.requested_by), "requested_by_name": names.get(r.requested_by),
                "created_at": r.created_at, "decided_at": r.decided_at.isoformat() if r.decided_at else None}


class _ApprovalEvent:
    """Lightweight (non-ORM) entity for the workflow engine's approval rules."""
    def __init__(self, organization_id, request_id, user_id, request_type, amount, status):
        self.organization_id = organization_id
        self.id = request_id
        self.user_id = user_id
        self.request_type = request_type
        self.amount = amount
        self.status = status
