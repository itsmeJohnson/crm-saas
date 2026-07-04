import uuid
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Territory(BaseModel):
    """A geographic sales unit forming a self-referential hierarchy:
    region > zone > city > area. `level` labels the tier; `parent_id` links up
    the tree (like Department's parent hierarchy). A territory may have a
    manager (User) and rolls up leads mapped to it via PIN codes.
    """
    __tablename__ = "territories"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_territory_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="region", nullable=False, index=True)  # region|zone|city|area
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("territories.id"), nullable=True, index=True)
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class Branch(BaseModel):
    """A physical/organizational branch office. Has a branch manager (User),
    an optional owning territory, a postal address, and a status. Leads flow to
    a branch (Lead.branch_id) and branch performance rolls those up.
    """
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_branch_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    branch_manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    territory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("territories.id"), nullable=True, index=True)
    address_line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_head_office: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class TerritoryPincode(BaseModel):
    """Maps a PIN/postal code to a territory (and optionally a branch). Drives
    automatic lead territory assignment: a lead's pin_code (or city) resolves to
    the mapped territory + branch. One PIN maps to one territory per org.
    """
    __tablename__ = "territory_pincodes"
    __table_args__ = (UniqueConstraint("organization_id", "pin_code", name="uq_territory_pincode_org_pin"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    pin_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("territories.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
