import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import UserRepository
from app.services.permission_service import PermissionService
from app.services.audit_service import AuditService
from app.core.security import get_password_hash
from app.models.user import User
from app.models.seat_history import SeatAssignmentHistory
from app.models.organization import Organization
from app.models.tenant_subscription import TenantSubscription

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def _get_licensed_seats(self, organization_id: uuid.UUID) -> int:
        # Check active subscription
        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()
        if sub:
            return sub.users_purchased
        
        # Fallback to organization max_users
        org_stmt = select(Organization.max_users).where(Organization.id == organization_id)
        org_res = await self.db.execute(org_stmt)
        val = org_res.scalar()
        return val if val is not None else 5

    async def _get_occupied_seats(self, organization_id: uuid.UUID) -> set[str]:
        stmt = select(User.seat_number).where(
            User.organization_id == organization_id,
            User.is_deleted == False,
            User.seat_number.isnot(None)
        )
        res = await self.db.execute(stmt)
        return {row for row in res.scalars().all() if row}

    async def _get_available_seat_numbers(self, organization_id: uuid.UUID) -> list[str]:
        limit = await self._get_licensed_seats(organization_id)
        occupied = await self._get_occupied_seats(organization_id)
        all_seats = {f"Seat-{i:03d}" for i in range(1, limit + 1)}
        return sorted(list(all_seats - occupied))

    async def is_team_leader(self, user: User) -> bool:
        """Check if the user is a Team Leader (Employee reporting to a Manager)."""
        if user.role != "Employee" or not user.reporting_to_id:
            return False
        parent_res = await self.db.execute(select(User.role).filter(User.id == user.reporting_to_id))
        parent_role = parent_res.scalar()
        return parent_role == "Manager"

    async def get_user_by_id(self, actor: User, user_id: uuid.UUID) -> User:
        """Fetch a specific user inside the same organization."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        user = await self.user_repo.get_user_by_id(actor.organization_id, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        if actor.id != user_id:
            is_tl = await self.is_team_leader(actor)
            PermissionService.check_user_management_permission(
                actor, user.role, user.reporting_to_id, is_tl
            )
        user.is_team_leader = await self.is_team_leader(user)
        return user

    async def create_user(self, actor: User, user_data: dict) -> User:
        """Create a user after verifying actor RBAC permissions."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        role = user_data.get("role", "Employee")
        reporting_to_id = user_data.get("reporting_to_id")
        if reporting_to_id and isinstance(reporting_to_id, str):
            reporting_to_id = uuid.UUID(reporting_to_id)
            user_data["reporting_to_id"] = reporting_to_id

        # Enforce RBAC Role Hierarchy
        is_tl = await self.is_team_leader(actor)
        
        # If actor is a Team Leader, they can only create Employees reporting directly to them
        if actor.role == "Employee":
            if not is_tl:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Telecallers cannot create users"
                )
            if role != "Employee":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Team Leaders can only create Employees"
                )
            if reporting_to_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Team Leaders can only create team members reporting to themselves"
                )
        
        PermissionService.check_user_management_permission(
            actor, role, reporting_to_id, is_tl
        )

        await self.validate_reporting_structure(
            user_id=None,
            role=role,
            reporting_to_id=reporting_to_id,
            organization_id=actor.organization_id
        )

        # Check global email uniqueness
        existing = await self.user_repo.get_by_email_global(user_data["email"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )

        # Allocate and assign seat
        available_seats = await self._get_available_seat_numbers(actor.organization_id)
        if not available_seats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No available seats. Please purchase additional seats or replace an existing inactive employee."
            )
        assigned_seat = available_seats[0]
        user_data["seat_number"] = assigned_seat

        if "password" in user_data:
            user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
        
        user = await self.user_repo.create_user(actor.organization_id, user_data)
        user.is_team_leader = await self.is_team_leader(user)

        # Create Seat Assignment History
        history = SeatAssignmentHistory(
            organization_id=actor.organization_id,
            seat_number=assigned_seat,
            user_id=user.id,
            action="Assigned",
            performed_by_id=actor.id,
            remarks="Assigned seat during user creation"
        )
        self.db.add(history)
        
        # Write Audit Log
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_CREATED",
            resource_type="user",
            resource_id=str(user.id),
            action_metadata={"email": user.email, "role": user.role, "seat_number": assigned_seat}
        )
        
        return user

    async def update_user(self, actor: User, user_id: uuid.UUID, update_data: dict) -> User:
        """Update user properties after verifying actor role permissions."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)

        # Enforce Hierarchy for role changes
        is_self = actor.id == user_id
        if is_self:
            if "role" in update_data and update_data["role"] != actor.role:
                if actor.role != "OrgAdmin":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You cannot change your own role"
                    )
            if "is_active" in update_data and not update_data["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot deactivate yourself"
                )
        else:
            is_tl = await self.is_team_leader(actor)
            PermissionService.check_user_management_permission(
                actor, target_user.role, target_user.reporting_to_id, is_tl
            )
            
            # TL constraints
            if actor.role == "Employee" and is_tl:
                if "role" in update_data and update_data["role"] != target_user.role:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Team Leaders cannot change the role of team members"
                    )
                if "reporting_to_id" in update_data and update_data["reporting_to_id"] != target_user.reporting_to_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Team Leaders cannot reassign team members"
                    )
            
            if "role" in update_data:
                PermissionService.check_user_management_permission(
                    actor, update_data["role"], update_data.get("reporting_to_id"), is_tl
                )

        # Validate reporting hierarchy if role or reporting_to_id is being updated
        if "role" in update_data or "reporting_to_id" in update_data:
            role = update_data.get("role", target_user.role)
            reporting_to_id = update_data.get("reporting_to_id", target_user.reporting_to_id)
            if reporting_to_id and isinstance(reporting_to_id, str):
                reporting_to_id = uuid.UUID(reporting_to_id)
            await self.validate_reporting_structure(
                user_id=user_id,
                role=role,
                reporting_to_id=reporting_to_id,
                organization_id=actor.organization_id
            )

        # Prevent demoting the final OrgAdmin
        if target_user.role == "OrgAdmin" and "role" in update_data and update_data["role"] != "OrgAdmin":
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the final OrgAdmin user of this organization"
                )

        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        updated = await self.user_repo.update_user(actor.organization_id, user_id, update_data)
        if updated:
            updated.is_team_leader = await self.is_team_leader(updated)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_UPDATED",
            resource_type="user",
            resource_id=str(user_id),
            action_metadata={"updated_fields": list(update_data.keys())}
        )

        return updated

    async def toggle_active(self, actor: User, user_id: uuid.UUID, is_active: bool, inactive_reason: str | None = None) -> User:
        """Activate or deactivate user account status."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)
        
        if actor.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You cannot deactivate yourself"
            )

        is_tl = await self.is_team_leader(actor)
        PermissionService.check_user_management_permission(
            actor, target_user.role, target_user.reporting_to_id, is_tl
        )

        # Prevent deactivating the last OrgAdmin
        if target_user.role == "OrgAdmin" and not is_active:
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the final OrgAdmin user of this organization"
                )

        # Handle seat licensing allocation / deactivation details
        assigned_seat = None
        if not is_active:
            # We are deactivating the user.
            target_user.inactive_reason = inactive_reason
            # Write seat history record for "Inactive"
            if target_user.seat_number:
                history = SeatAssignmentHistory(
                    organization_id=actor.organization_id,
                    seat_number=target_user.seat_number,
                    user_id=target_user.id,
                    action="Inactive",
                    performed_by_id=actor.id,
                    remarks=f"User marked Inactive. Reason: {inactive_reason or 'No reason provided'}"
                )
                self.db.add(history)
        else:
            # We are activating the user.
            target_user.inactive_reason = None
            if not target_user.seat_number:
                # User currently has no seat (was replaced). We must assign them a new seat!
                available_seats = await self._get_available_seat_numbers(actor.organization_id)
                if not available_seats:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No available seats to activate this user. Please purchase additional seats."
                    )
                assigned_seat = available_seats[0]
                target_user.seat_number = assigned_seat

                history = SeatAssignmentHistory(
                    organization_id=actor.organization_id,
                    seat_number=assigned_seat,
                    user_id=target_user.id,
                    action="Assigned",
                    performed_by_id=actor.id,
                    remarks="Assigned seat during user activation"
                )
                self.db.add(history)

        updated = await self.user_repo.toggle_active(actor.organization_id, user_id, is_active)
        if updated:
            if not is_active:
                updated.inactive_reason = inactive_reason
            else:
                updated.inactive_reason = None
                if assigned_seat:
                    updated.seat_number = assigned_seat
            
            updated.is_team_leader = await self.is_team_leader(updated)

        action_name = "USER_ACTIVATED" if is_active else "USER_DEACTIVATED"
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action=action_name,
            resource_type="user",
            resource_id=str(user_id),
            action_metadata={"inactive_reason": inactive_reason} if not is_active else {}
        )

        return updated

    async def soft_delete_user(self, actor: User, user_id: uuid.UUID) -> User:
        """Soft delete a user from organization listing."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)
        
        if actor.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You cannot delete yourself"
            )

        is_tl = await self.is_team_leader(actor)
        PermissionService.check_user_management_permission(
            actor, target_user.role, target_user.reporting_to_id, is_tl
        )

        # Prevent deleting the last OrgAdmin
        if target_user.role == "OrgAdmin":
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the final OrgAdmin user of this organization"
                )

        deleted = await self.user_repo.soft_delete_user(actor.organization_id, user_id)
        if deleted:
            deleted.is_team_leader = await self.is_team_leader(deleted)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_DELETED",
            resource_type="user",
            resource_id=str(user_id)
        )

        return deleted

    async def paginate_users(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None
    ) -> Tuple[Sequence[User], int]:
        """Fetch paginated, searchable list of users belonging to the tenant."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        reporting_to_id = None
        if actor.role == "Employee":
            is_tl = False
            if actor.reporting_to_id:
                # Check if the parent role is Manager (so actor is TL)
                parent_res = await self.db.execute(select(User.role).filter(User.id == actor.reporting_to_id))
                parent_role = parent_res.scalar()
                if parent_role == "Manager":
                    is_tl = True
            
            if not is_tl:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have enough privileges"
                )
            reporting_to_id = actor.id

        records, total = await self.user_repo.paginate_users(
            actor.organization_id, skip, limit, search_query, role, is_active, reporting_to_id
        )
        for u in records:
            u.is_team_leader = await self.is_team_leader(u)
        return records, total

    async def get_downline_user_ids(self, actor: User) -> set[uuid.UUID]:
        """Fetch all downline user IDs in actor's reporting chain recursively."""
        return await self.get_downline_user_ids_by_id(actor.organization_id, actor.id)

    async def get_downline_user_ids_by_id(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> set[uuid.UUID]:
        """Fetch all downline user IDs in a user's reporting chain recursively."""
        query = select(User.id, User.reporting_to_id).where(
            User.organization_id == organization_id,
            User.is_deleted == False
        )
        result = await self.db.execute(query)
        rows = result.all()
        
        parent_to_children = {}
        for uid, pid in rows:
            if pid is not None:
                parent_to_children.setdefault(pid, []).append(uid)
                
        downlines = set()
        queue = [user_id]
        while queue:
            curr = queue.pop(0)
            children = parent_to_children.get(curr, [])
            for child in children:
                if child not in downlines:
                    downlines.add(child)
                    queue.append(child)
        return downlines

    async def validate_reporting_structure(
        self,
        user_id: uuid.UUID | None,
        role: str,
        reporting_to_id: uuid.UUID | None,
        organization_id: uuid.UUID
    ) -> None:
        """
        Validate the strict 4-tier reporting line:
        - OrgAdmin cannot report to anyone.
        - Manager must report to an OrgAdmin.
        - Employee (TL) must report to a Manager.
        - Employee (Telecaller) must report to a TL (Employee who reports to a Manager).
        """
        if role == "OrgAdmin":
            if reporting_to_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OrgAdmin cannot report to anyone"
                )
            return

        if reporting_to_id is None:
            return

        if user_id and reporting_to_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user cannot report to themselves"
            )

        # Prevent circular reporting dependency
        if user_id:
            downlines = await self.get_downline_user_ids_by_id(organization_id, user_id)
            if reporting_to_id in downlines:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Circular reporting dependency detected: target manager reports to this user"
                )

        # Fetch parent
        parent = await self.user_repo.get_user_by_id(organization_id, reporting_to_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reporting user not found or belongs to another organization"
            )

        if role == "Manager":
            if parent.role != "OrgAdmin":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Managers must report to a Super Admin (OrgAdmin)"
                )

        elif role == "Employee":
            if parent.role == "Manager":
                # Valid TL
                pass
            elif parent.role == "Employee":
                # Parent is Employee, must be a TL (so parent must report to a Manager)
                if not parent.reporting_to_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Telecallers must report to a Team Leader who reports to a Manager"
                    )
                grandparent = await self.user_repo.get_user_by_id(organization_id, parent.reporting_to_id)
                if not grandparent or grandparent.role != "Manager":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Telecallers must report to a Team Leader who reports to a Manager"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Employees must report to either a Manager (TL) or a Team Leader (Agent)"
                )

    async def replace_employee(
        self,
        actor: User,
        old_user_id: uuid.UUID,
        new_user_data: dict,
        ip_address: str | None = None,
        browser_info: str | None = None
    ) -> Tuple[User, str]:
        """
        Replace an inactive employee with a new employee under the same seat.
        """
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )

        # 1. Fetch old employee
        old_user = await self.user_repo.get_user_by_id(actor.organization_id, old_user_id)
        if not old_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Old employee not found"
            )

        # 2. Check if old employee is inactive and holds a seat
        if old_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee must be inactive (marked Resigned/Terminated etc.) to be replaced."
            )
        if not old_user.seat_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee has no seat number assigned. They cannot be replaced."
            )

        # 3. Enforce RBAC permissions to manage this role
        is_tl = await self.is_team_leader(actor)
        role = new_user_data.get("role", "Employee")
        reporting_to_id = new_user_data.get("reporting_to_id")
        if reporting_to_id and isinstance(reporting_to_id, str):
            reporting_to_id = uuid.UUID(reporting_to_id)
            new_user_data["reporting_to_id"] = reporting_to_id

        # Check actor management permission over target role
        PermissionService.check_user_management_permission(
            actor, role, reporting_to_id, is_tl
        )

        # Validate reporting structure for new user
        await self.validate_reporting_structure(
            user_id=None,
            role=role,
            reporting_to_id=reporting_to_id,
            organization_id=actor.organization_id
        )

        # 4. Check global email uniqueness for new user
        existing = await self.user_repo.get_by_email_global(new_user_data["email"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )

        # 5. Capture the seat
        seat_to_transfer = old_user.seat_number

        # 6. Deactivate old login's seat association
        old_user.seat_number = None

        # 7. Create new user with the transferred seat
        new_user_data["seat_number"] = seat_to_transfer
        if "password" in new_user_data:
            new_user_data["hashed_password"] = get_password_hash(new_user_data.pop("password"))

        new_user = await self.user_repo.create_user(actor.organization_id, new_user_data)
        new_user.is_team_leader = await self.is_team_leader(new_user)

        # 8. Record seat release for old user
        release_history = SeatAssignmentHistory(
            organization_id=actor.organization_id,
            seat_number=seat_to_transfer,
            user_id=old_user.id,
            action="Released",
            performed_by_id=actor.id,
            remarks=f"Released seat {seat_to_transfer} due to employee replacement by {new_user.email}"
        )
        self.db.add(release_history)

        # 9. Record seat assignment for new user
        assign_history = SeatAssignmentHistory(
            organization_id=actor.organization_id,
            seat_number=seat_to_transfer,
            user_id=new_user.id,
            action="Assigned",
            performed_by_id=actor.id,
            remarks=f"Assigned seat {seat_to_transfer} from replaced employee {old_user.email}"
        )
        self.db.add(assign_history)

        # 10. Write Audit Log
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="EMPLOYEE_REPLACED",
            resource_type="user",
            resource_id=str(new_user.id),
            action_metadata={
                "old_employee_id": str(old_user.id),
                "old_employee_email": old_user.email,
                "new_employee_id": str(new_user.id),
                "new_employee_email": new_user.email,
                "seat_number": seat_to_transfer,
                "ip_address": ip_address,
                "browser": browser_info
            }
        )

        success_msg = f"Employee Replaced Successfully. Seat transferred successfully. No additional billing applied."
        return new_user, success_msg

    async def get_seat_utilization(self, organization_id: uuid.UUID) -> dict:
        licensed = await self._get_licensed_seats(organization_id)
        
        # Get active users count (is_active = True and seat_number IS NOT NULL)
        active_stmt = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_deleted == False,
            User.is_active == True,
            User.seat_number.isnot(None)
        )
        active_res = await self.db.execute(active_stmt)
        active_users = active_res.scalar() or 0

        # Get inactive assigned seats count (is_active = False and seat_number IS NOT NULL)
        inactive_stmt = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_deleted == False,
            User.is_active == False,
            User.seat_number.isnot(None)
        )
        inactive_res = await self.db.execute(inactive_stmt)
        inactive_assigned_seats = inactive_res.scalar() or 0

        available_new_seats = max(0, licensed - (active_users + inactive_assigned_seats))
        replace_employee_available = inactive_assigned_seats

        return {
            "licensed_seats": licensed,
            "active_users": active_users,
            "inactive_assigned_seats": inactive_assigned_seats,
            "available_new_seats": available_new_seats,
            "replace_employee_available": replace_employee_available
        }

    async def get_seat_history(self, organization_id: uuid.UUID) -> list[SeatAssignmentHistory]:
        stmt = select(SeatAssignmentHistory).where(
            SeatAssignmentHistory.organization_id == organization_id
        ).order_by(SeatAssignmentHistory.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_inactive_employees(self, organization_id: uuid.UUID) -> list[User]:
        stmt = select(User).where(
            User.organization_id == organization_id,
            User.is_deleted == False,
            User.is_active == False,
            User.seat_number.isnot(None)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
