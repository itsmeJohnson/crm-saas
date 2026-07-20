import uuid
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CustomRole(BaseModel):
    """A tenant-defined role overlaying the fixed base roles.

    Users keep their `role` string (SuperAdmin/OrgAdmin/Manager/Employee) —
    all legacy checks continue to run. A custom role only *adds* a permission
    matrix on top: `base_role` seeds the default matrix (inheritance), and
    role_permissions / field_permissions rows override it.
    """
    __tablename__ = "custom_roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_custom_role_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_role: Mapped[str] = mapped_column(String(20), default="Employee", nullable=False)  # Employee|Manager|OrgAdmin
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # seeded template
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active|archived
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class RolePermission(BaseModel):
    """One resource×action cell of a custom role's permission matrix.

    `scope` bounds record visibility for view/edit/delete: own|team|department|all.
    Missing cells fall back to the base-role default matrix (inheritance).
    """
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "resource", "action", name="uq_role_perm_cell"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)  # view|create|edit|delete|export|import|assign|bulk
    allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope: Mapped[str | None] = mapped_column(String(20), nullable=True)  # own|team|department|all (view/edit/delete)


class FieldPermission(BaseModel):
    """Field-level access for a resource under a custom role: read|write|hidden."""
    __tablename__ = "field_permissions"
    __table_args__ = (UniqueConstraint("role_id", "resource", "field_name", name="uq_field_perm"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    access: Mapped[str] = mapped_column(String(10), default="write", nullable=False)  # read|write|hidden
