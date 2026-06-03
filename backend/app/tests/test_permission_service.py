import pytest
from fastapi import HTTPException
from app.services.permission_service import PermissionService
from app.models.user import User

def test_verify_role_hierarchy():
    # OrgAdmin role checks
    assert PermissionService.verify_role_hierarchy("OrgAdmin", "OrgAdmin") is True
    assert PermissionService.verify_role_hierarchy("OrgAdmin", "Manager") is True
    assert PermissionService.verify_role_hierarchy("OrgAdmin", "Employee") is True

    # Manager role checks
    assert PermissionService.verify_role_hierarchy("Manager", "OrgAdmin") is False
    assert PermissionService.verify_role_hierarchy("Manager", "Manager") is False
    assert PermissionService.verify_role_hierarchy("Manager", "Employee") is True

    # Employee role checks
    assert PermissionService.verify_role_hierarchy("Employee", "OrgAdmin") is False
    assert PermissionService.verify_role_hierarchy("Employee", "Employee") is False

def test_check_user_management_permission():
    # Mock users
    admin = User(role="OrgAdmin", is_active=True)
    manager = User(role="Manager", is_active=True)
    employee = User(role="Employee", is_active=True)
    inactive_admin = User(role="OrgAdmin", is_active=False)

    # 1. Active OrgAdmin can manage any role
    PermissionService.check_user_management_permission(admin, "Employee")
    PermissionService.check_user_management_permission(admin, "Manager")
    PermissionService.check_user_management_permission(admin, "OrgAdmin")

    # 2. Active Manager can manage Employee
    PermissionService.check_user_management_permission(manager, "Employee")
    
    # 3. Active Manager cannot manage OrgAdmin or Manager
    with pytest.raises(HTTPException) as exc_info:
        PermissionService.check_user_management_permission(manager, "OrgAdmin")
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        PermissionService.check_user_management_permission(manager, "Manager")
    assert exc_info.value.status_code == 403

    # 4. Active Employee cannot manage anyone
    with pytest.raises(HTTPException) as exc_info:
        PermissionService.check_user_management_permission(employee, "Employee")
    assert exc_info.value.status_code == 403

    # 5. Inactive actor is blocked entirely
    with pytest.raises(HTTPException) as exc_info:
        PermissionService.check_user_management_permission(inactive_admin, "Employee")
    assert exc_info.value.status_code == 403
    assert "deactivated" in exc_info.value.detail
