import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Index, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.models.base import BaseModel
from app.models.types import NormalizedEmail
from app.core.email_utils import normalize_email

class User(BaseModel):
    __tablename__ = "users"

    __table_args__ = (
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    @validates("email")
    def validate_email(self, key, value):
        return normalize_email(value)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(NormalizedEmail(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="Employee")  # SuperAdmin, OrgAdmin, Manager, Employee
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(default=1, nullable=False)
    is_invited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reporting_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    
    # Password Reset
    reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # C3: must be timezone-aware. The code writes tz-aware UTC datetimes; a naive
    # ("timestamp without time zone") column makes asyncpg raise DataError on write
    # and compare (breaks the whole reset flow on Postgres). Matches base.py timestamps.
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Seat Licensing Extensions
    seat_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    inactive_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Department membership (nullable — orthogonal to the reporting hierarchy;
    # existing users default to NULL, preserving backward compatibility). use_alter
    # breaks the users↔departments FK cycle for metadata create/drop ordering.
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", use_alter=True, name="fk_users_department"), nullable=True, index=True)
    # Optional custom-role overlay (nullable — legacy role checks stay authoritative
    # when NULL). use_alter breaks the users↔custom_roles FK cycle like departments.
    custom_role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("custom_roles.id", use_alter=True, name="fk_users_custom_role"), nullable=True, index=True)

    # MFA / TOTP
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_backup_codes: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # JSON list
    calendar_feed_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # secret for .ics subscribe URL

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    reporting_to: Mapped["User | None"] = relationship("User", remote_side="User.id", back_populates="downlines")
    downlines: Mapped[list["User"]] = relationship("User", back_populates="reporting_to")
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
