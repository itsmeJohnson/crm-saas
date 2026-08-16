import pytest
import unicodedata
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select, text, cast
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email_utils import normalize_email
from app.models.user import User
from app.models.invitation import UserInvitation
from app.models.types import NormalizedEmail
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.invitation_repository import InvitationRepository
from app.services.user_service import UserService
from app.core.security import get_password_hash, create_access_token

# Mock email module capture
import app.services.email_service as email_service_mod

@pytest.fixture(autouse=True)
def capture_email(monkeypatch):
    sent = {}
    def fake_send_email(to_email, subject, template_name, context):
        sent["to"] = to_email
        sent["subject"] = subject
        sent["context"] = context
    monkeypatch.setattr(email_service_mod, "send_email", fake_send_email)
    return sent

# ---------------------------------------------------------------------------
# 1. Pure Unit Tests for normalize_email
# ---------------------------------------------------------------------------

def test_normalize_email_basic():
    # Trim and lowercase
    assert normalize_email("  USER@Example.Com ") == "user@example.com"
    # NFC normalization (composed characters)
    # \u00e9 is 'é' (composed). \u0065\u0301 is 'e' + combining acute accent (decomposed).
    decomposed = "caf\u0065\u0301@example.com"
    composed = "caf\u00e9@example.com"
    assert normalize_email(decomposed) == composed

def test_normalize_email_empty():
    assert normalize_email(None) is None
    assert normalize_email("   ") is None

def test_normalize_email_subaddressing():
    # Plus tags and dots should be preserved
    assert normalize_email("john.doe+tag@example.com") == "john.doe+tag@example.com"
    assert normalize_email("  John.Doe+Tag@Example.Com  ") == "john.doe+tag@example.com"

def test_normalize_email_idempotency():
    email = "  Test.User+Sub@Gmail.COM  "
    first = normalize_email(email)
    second = normalize_email(first)
    assert first == second
    assert second == "test.user+sub@gmail.com"


# ---------------------------------------------------------------------------
# 2. Unit Tests for SQLAlchemy TypeDecorator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_type_decorator_storage_and_query(db: AsyncSession):
    # Setup organization
    org = await OrganizationRepository(db).create({"name": "Test Org", "slug": "test-org"})
    await db.commit()

    # Save user with mixed-case and trailing spaces
    raw_email = "  Decorator.User+1@Example.com "
    user = User(
        organization_id=org.id,
        email=raw_email,
        hashed_password="hash",
        first_name="Deco",
        last_name="User",
        role="Employee",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    await db.commit()

    # Query directly from DB using cast to String to verify raw stored value is lowercased
    res = await db.execute(select(cast(User.email, sa.String)).where(User.id == user.id))
    stored_email = res.scalar()
    assert stored_email == "decorator.user+1@example.com"

    # Query using SQLAlchemy query with mixed case
    # This checks process_bind_param maps the lookup value to lowercase
    stmt = select(User).where(User.email == " DECORATOR.user+1@EXAMPLE.COM  ")
    res = await db.execute(stmt)
    found = res.scalar_one_or_none()
    assert found is not None
    assert found.id == user.id
    assert found.email == "decorator.user+1@example.com"


# ---------------------------------------------------------------------------
# 3. Flow Validation Tests (Signup, Login, Forgot Password, Reset Password,
#    Invitation Create, Invitation Accept, Admin Create, Update, Replace, Search)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_normalization_flows(client: AsyncClient, db: AsyncSession, capture_email: dict, monkeypatch):
    # Mock SMTP for password reset
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    # A. SIGNUP FLOW
    # Register a new tenant with mixed-case admin email
    reg_payload = {
        "company_name": "Normalization Corp",
        "slug": "norm-corp",
        "admin_email": " Founder.Admin@NormCorp.com ",
        "admin_password": "securepassword123",
        "first_name": "Founder",
        "last_name": "Admin",
        "licensed_seats": 10,
        "contract_months": 3
    }
    signup_res = await client.post("/api/v1/auth/public-register", json=reg_payload)
    assert signup_res.status_code == 201
    signup_data = signup_res.json()
    assert signup_data["access_token"] is not None

    # Fetch admin user from DB and assert email is stored in lowercase
    user_repo = UserRepository(db)
    admin_user = await user_repo.get_by_email_global("founder.admin@normcorp.com")
    assert admin_user is not None
    assert admin_user.email == "founder.admin@normcorp.com"

    # Verify duplicate signup under case-variant is rejected
    dup_signup_res = await client.post("/api/v1/auth/public-register", json={
        **reg_payload,
        "admin_email": "FOUNDER.ADMIN@normcorp.com",
        "slug": "norm-corp-dup"
    })
    assert dup_signup_res.status_code == 400
    assert "Email already registered" in dup_signup_res.json()["detail"]


    # B. LOGIN FLOW
    # Authenticate using different casing
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "  FoUnDeR.aDmIn@nOrMcOrP.cOm ",
        "password": "securepassword123"
    })
    assert login_res.status_code == 200
    login_tokens = login_res.json()
    assert "access_token" in login_tokens
    auth_headers = {"Authorization": f"Bearer {login_tokens['access_token']}"}


    # C. FORGOT PASSWORD FLOW
    # Request reset token using mixed-case email
    forgot_res = await client.post("/api/v1/auth/forgot-password", json={
        "email": " FOUNDER.admin@NORMCORP.COM "
    })
    assert forgot_res.status_code == 200
    # Retrieve reset token from email capture context
    assert capture_email.get("to") == "founder.admin@normcorp.com"
    reset_url = capture_email["context"]["reset_url"]
    assert "token=" in reset_url
    reset_token = reset_url.split("token=")[1]


    # D. RESET PASSWORD FLOW
    # Reset password with retrieved token
    reset_res = await client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "password": "NewSuperPassword123"
    })
    assert reset_res.status_code == 200

    # Verify login works with new password and mixed-case email
    login_new_res = await client.post("/api/v1/auth/login", json={
        "email": "founder.admin@normcorp.com",
        "password": "NewSuperPassword123"
    })
    assert login_new_res.status_code == 200
    # Update auth_headers with new token after password reset to avoid 401 token_version check
    auth_headers = {"Authorization": f"Bearer {login_new_res.json()['access_token']}"}


    # E. INVITATION CREATE FLOW
    # Invite an employee using mixed-case email
    invite_payload = {
        "email": " Invited.Employee@Normcorp.com  ",
        "role": "Employee"
    }
    invite_res = await client.post("/api/v1/users/invitations", json=invite_payload, headers=auth_headers)
    assert invite_res.status_code == 201
    invite_data = invite_res.json()
    assert invite_data["email"] == "invited.employee@normcorp.com"
    invite_token = invite_data["token"]

    # Verify duplicate invite under case-variant is rejected
    dup_invite_res = await client.post("/api/v1/users/invitations", json={
        "email": "INVITED.employee@NORMcorp.com",
        "role": "Employee"
    }, headers=auth_headers)
    assert dup_invite_res.status_code == 400
    assert "pending invitation already exists" in dup_invite_res.json()["detail"].lower()


    # F. INVITATION ACCEPT FLOW
    # Accept the invitation
    accept_payload = {
        "token": invite_token,
        "password": "invitedpassword123",
        "first_name": "Invited",
        "last_name": "Employee"
    }
    accept_res = await client.post("/api/v1/users/invitations/accept", json=accept_payload)
    assert accept_res.status_code == 200
    accepted_data = accept_res.json()
    assert accepted_data["email"] == "invited.employee@normcorp.com"

    # Query user directly from DB to verify it is lowercase
    invited_user = await user_repo.get_by_email_global("invited.employee@normcorp.com")
    assert invited_user is not None
    assert invited_user.email == "invited.employee@normcorp.com"


    # G. ADMIN CREATE USER FLOW
    # Admin creates user with mixed case
    admin_create_payload = {
        "email": " Admin.Created@NormCorp.com ",
        "first_name": "Admin",
        "last_name": "Created",
        "role": "Employee",
        "password": "userpassword123",
        "organization_id": str(admin_user.organization_id)
    }
    admin_create_res = await client.post("/api/v1/users/", json=admin_create_payload, headers=auth_headers)
    assert admin_create_res.status_code == 201
    created_user_data = admin_create_res.json()
    assert created_user_data["email"] == "admin.created@normcorp.com"

    # Duplicate create fails
    dup_create_res = await client.post("/api/v1/users/", json={
        **admin_create_payload,
        "email": "ADMIN.CREATED@NORMCORP.COM"
    }, headers=auth_headers)
    assert dup_create_res.status_code == 400
    assert "Email already registered" in dup_create_res.json()["detail"]


    # H. UPDATE USER FLOW
    # Update first_name/last_name of created user
    created_user_id = created_user_data["id"]
    update_res = await client.patch(f"/api/v1/users/{created_user_id}", json={
        "first_name": "UpdatedAdminCreated"
    }, headers=auth_headers)
    assert update_res.status_code == 200
    updated_user_data = update_res.json()
    assert updated_user_data["email"] == "admin.created@normcorp.com"


    # I. REPLACE EMPLOYEE FLOW
    # We first setup a subscription with a seat to replace (already done during register_tenant which seeds standard seat)
    # Assign a seat number to the employee in the database so they can be replaced
    invited_user.seat_number = "1"
    db.add(invited_user)
    await db.commit()

    # Deactivate the invited employee
    deactivate_res = await client.patch(f"/api/v1/users/{invited_user.id}/status?is_active=false", headers=auth_headers)
    assert deactivate_res.status_code == 200

    # Call UserService replace_employee manually (the service boundary)
    user_service = UserService(db)
    replacement_data = {
        "email": " Replacement.User@NormCorp.com ",
        "first_name": "Replacement",
        "last_name": "User",
        "role": "Employee",
        "password": "securepassword123",
        "phone": "+91 99999 99999"
    }
    # Fetch admin user from DB fresh to avoid session issues
    admin_user_fresh = await user_repo.get_user_by_id(admin_user.organization_id, admin_user.id)
    # Ensure plan subscription has purchased seats setup
    # In test environment, register_tenant sets up everything. Let's run replacement
    new_user, notification = await user_service.replace_employee(
        actor=admin_user_fresh,
        old_user_id=invited_user.id,
        new_user_data=replacement_data,
        ip_address="127.0.0.1",
        browser_info="Mozilla/5.0"
    )
    assert new_user is not None
    assert new_user.email == "replacement.user@normcorp.com"


    # J. USER SEARCH FLOW
    # Search for user via lists API using mixed-case query
    search_res = await client.get("/api/v1/users/?search=REPLACEMENT.USER", headers=auth_headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) >= 1
    emails_found = [u["email"] for u in search_data]
    assert "replacement.user@normcorp.com" in emails_found


# ---------------------------------------------------------------------------
# 4. Migration Testing (Pre-flight collision & De-duplication)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_logic(db: AsyncSession):
    from alembic.ddl import impl
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    # We manually simulate the migration upgrade steps in a sub-transaction
    # First, test the pre-flight check raises Exception on duplicates
    org = await OrganizationRepository(db).create({"name": "Migration Org", "slug": "mig-org"})
    await db.commit()

    # Temporarily drop the unique index so we can seed duplicates for the pre-flight check test
    await db.execute(text("DROP INDEX uq_users_email_lower"))
    await db.commit()

    # Insert duplicate emails with different cases directly using raw SQL to bypass the ORM NormalizedEmail decorator
    # Email 1: dup@mig.com
    await db.execute(
        text("INSERT INTO users (id, organization_id, email, hashed_password, role, is_active, is_verified, token_version, is_invited, created_at, updated_at, is_deleted, mfa_enabled) "
             "VALUES (:id1, :org_id, 'dup@mig.com', 'hash', 'Employee', true, true, 1, false, :now, :now, false, false)"),
        {"id1": "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1", "org_id": str(org.id), "now": datetime.now(timezone.utc)}
    )
    # Email 2: DUP@mig.com (case-variant duplicate!)
    await db.execute(
        text("INSERT INTO users (id, organization_id, email, hashed_password, role, is_active, is_verified, token_version, is_invited, created_at, updated_at, is_deleted, mfa_enabled) "
             "VALUES (:id2, :org_id, 'DUP@mig.com', 'hash', 'Employee', true, true, 1, false, :now, :now, false, false)"),
        {"id2": "b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2", "org_id": str(org.id), "now": datetime.now(timezone.utc)}
    )
    await db.commit()

    # Import the migration module dynamically to execute its upgrade steps
    import importlib.util
    import sys
    
    mig_path = "/app/alembic/versions/email_normalize_0001_add_centralized_email_normalization.py"
    spec = importlib.util.spec_from_file_location("email_normalize_0001", mig_path)
    mig_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig_mod)

    # We mock alembic `op` to run within our current session via run_sync to allow synchronous execution
    class ProxyConnection:
        def __init__(self, conn):
            self.conn = conn
            self.dialect = conn.dialect
        def execute(self, sql, *args, **kwargs):
            sql_str = str(sql)
            if "CREATE UNIQUE INDEX" in sql_str:
                # bypass creating unique index in unit test db (since we already defined uq_users_email_lower on python model args!)
                return None
            return self.conn.execute(sql, *args, **kwargs)

    class FakeOp:
        def __init__(self, sync_session, mock_index=False):
            self.sync_session = sync_session
            self.mock_index = mock_index
        def get_bind(self):
            conn = self.sync_session.connection()
            if self.mock_index:
                return ProxyConnection(conn)
            return conn

    def run_upgrade(sync_session):
        mig_mod.op = FakeOp(sync_session, mock_index=False)
        mig_mod.upgrade()

    # Run upgrade. It must raise Exception due to duplicates!
    with pytest.raises(Exception) as exc_info:
        await db.run_sync(run_upgrade)
    assert "duplicate normalized emails were found" in str(exc_info.value)
    assert "dup@mig.com" in str(exc_info.value)

    # Clean up the duplicates so we can test the rest
    await db.execute(text("DELETE FROM users WHERE email IN ('dup@mig.com', 'DUP@mig.com')"))
    await db.commit()

    # Now let's test invitation de-duplication
    # Create two pending invitations under different cases
    # Invitation 1: created 2 hours ago
    t1 = datetime.now(timezone.utc) - timedelta(hours=2)
    await db.execute(
        text("INSERT INTO user_invitations (id, organization_id, email, role, token, expires_at, accepted, revoked, created_by, created_at) "
             "VALUES (:id1, :org_id, 'invite@mig.com', 'Employee', 'token1', :expires, false, false, :admin_id, :t1)"),
        {"id1": "c3c3c3c3-c3c3-c3c3-c3c3-c3c3c3c3c3c3", "org_id": str(org.id), "expires": datetime.now(timezone.utc) + timedelta(days=1), "admin_id": "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1", "t1": t1}
    )
    # Invitation 2: created 1 hour ago (newest!)
    t2 = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.execute(
        text("INSERT INTO user_invitations (id, organization_id, email, role, token, expires_at, accepted, revoked, created_by, created_at) "
             "VALUES (:id2, :org_id, 'INVITE@mig.com', 'Employee', 'token2', :expires, false, false, :admin_id, :t2)"),
        {"id2": "d4d4d4d4-d4d4-d4d4-d4d4-d4d4d4d4d4d4", "org_id": str(org.id), "expires": datetime.now(timezone.utc) + timedelta(days=1), "admin_id": "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1", "t2": t2}
    )
    await db.commit()

    def run_upgrade_success(sync_session):
        mig_mod.op = FakeOp(sync_session, mock_index=True)
        mig_mod.upgrade()

    # Execute upgrade. It should run successfully now!
    await db.run_sync(run_upgrade_success)
    await db.commit()

    # Assert that the older invitation (c3c3...) was deleted and only the newest (d4d4...) remains
    res_invs = (await db.execute(text("SELECT id, email FROM user_invitations"))).fetchall()
    assert len(res_invs) == 1
    assert res_invs[0][0] == "d4d4d4d4-d4d4-d4d4-d4d4-d4d4d4d4d4d4"
    # Also assert that the remaining invitation's email has been normalized to lowercase
    assert res_invs[0][1] == "invite@mig.com"

    # Clean up invitations
    await db.execute(text("DELETE FROM user_invitations"))
    await db.commit()
