import pytest
import uuid
import datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.models.seat_history import SeatAssignmentHistory
from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan

@pytest.mark.asyncio
async def test_seat_licensing_and_replace_employee(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    user_service = UserService(db)

    # 1. Setup organization
    org = await org_repo.create({"name": "Licensing Org", "slug": "licensing-org", "max_users": 3})
    await db.commit()

    # Create Plan and Subscription with 3 seats
    plan = Plan(
        name="Growth",
        max_users=3,
        max_admins=2,
        max_managers=2,
        max_team_leads=2,
        max_employees=10
    )
    db.add(plan)
    await db.flush()

    subscription = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        start_date=datetime.datetime.now(datetime.timezone.utc),
        end_date=datetime.datetime.now(datetime.timezone.utc),
        users_purchased=3
    )
    db.add(subscription)
    await db.commit()

    # 2. Create users and verify seat assignment
    # Create OrgAdmin (takes Seat-001)
    admin = await user_repo.create_user(org.id, {
        "email": "admin@licensing.com",
        "hashed_password": "hash",
        "first_name": "Admin",
        "last_name": "User",
        "role": "OrgAdmin",
        "is_active": True
    })
    # Since we bypassed user_service, let's assign seat manually or create via user_service
    # Actually, let's assign Seat-001 manually to admin to simulate initial setup
    admin.seat_number = "Seat-001"
    db.add(admin)
    db.add(SeatAssignmentHistory(
        organization_id=org.id,
        seat_number="Seat-001",
        user_id=admin.id,
        action="Assigned",
        performed_by_id=admin.id,
        remarks="Manual assignment"
    ))
    await db.commit()

    # Create Manager (takes Seat-002) using user_service
    manager_data = {
        "email": "manager@licensing.com",
        "first_name": "Manager",
        "last_name": "User",
        "role": "Manager",
        "password": "securepassword123"
    }
    manager = await user_service.create_user(admin, manager_data)
    assert manager.seat_number == "Seat-002"

    # Create Employee (takes Seat-003) using user_service
    employee_data = {
        "email": "emp@licensing.com",
        "first_name": "Employee",
        "last_name": "User",
        "role": "Employee",
        "reporting_to_id": manager.id,
        "password": "securepassword123"
    }
    employee = await user_service.create_user(admin, employee_data)
    assert employee.seat_number == "Seat-003"

    # 3. Verify seat limit validation: try creating 4th user when limit is 3
    extra_emp_data = {
        "email": "extra@licensing.com",
        "first_name": "Extra",
        "last_name": "User",
        "role": "Employee",
        "reporting_to_id": manager.id,
        "password": "securepassword123"
    }
    with pytest.raises(HTTPException) as exc_info:
        await user_service.create_user(admin, extra_emp_data)
    assert exc_info.value.status_code == 400
    assert "No available seats" in exc_info.value.detail

    # 4. Check seat utilization
    util = await user_service.get_seat_utilization(org.id)
    assert util["licensed_seats"] == 3
    assert util["active_users"] == 3
    assert util["inactive_assigned_seats"] == 0
    assert util["available_new_seats"] == 0
    assert util["replace_employee_available"] == 0

    # 5. Inactivate Employee
    await user_service.toggle_active(admin, employee.id, False, "Resigned")
    assert employee.is_active is False
    assert employee.inactive_reason == "Resigned"
    assert employee.seat_number == "Seat-003"  # Still occupies the seat

    # Check utilization after inactivation
    util = await user_service.get_seat_utilization(org.id)
    assert util["active_users"] == 2
    assert util["inactive_assigned_seats"] == 1
    assert util["available_new_seats"] == 0
    assert util["replace_employee_available"] == 1

    # Check inactive employees list
    inactive_list = await user_service.get_inactive_employees(org.id)
    assert len(inactive_list) == 1
    assert inactive_list[0].id == employee.id

    # 6. Replace Employee
    replacement_data = {
        "email": "new_hire@licensing.com",
        "first_name": "New",
        "last_name": "Hire",
        "role": "Employee",
        "reporting_to_id": manager.id,
        "password": "securepassword123",
        "phone": "+91 98765 43210"
    }
    new_user, notification = await user_service.replace_employee(
        actor=admin,
        old_user_id=employee.id,
        new_user_data=replacement_data,
        ip_address="127.0.0.1",
        browser_info="Mozilla/5.0"
    )
    assert new_user.seat_number == "Seat-003"
    assert employee.seat_number is None  # Released
    assert "Employee Replaced Successfully" in notification

    # Check utilization after replacement
    util = await user_service.get_seat_utilization(org.id)
    assert util["active_users"] == 3
    assert util["inactive_assigned_seats"] == 0
    assert util["available_new_seats"] == 0
    assert util["replace_employee_available"] == 0

    # 7. Check seat history logs
    history = await user_service.get_seat_history(org.id)
    # Check that we have a Released and Assigned action for Seat-003
    actions = [h.action for h in history if h.seat_number == "Seat-003"]
    assert "Released" in actions
    assert "Assigned" in actions

    # 8. Test reactivating the replaced employee when no seats are available
    with pytest.raises(HTTPException) as exc_info:
        await user_service.toggle_active(admin, employee.id, True)
    assert exc_info.value.status_code == 400
    assert "No available seats" in exc_info.value.detail
