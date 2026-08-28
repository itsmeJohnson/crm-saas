import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, validates
from app.models.base import BaseModel
from app.models.types import NormalizedEmail
from app.core.email_utils import normalize_email

class TrialRequest(BaseModel):
    __tablename__ = "trial_requests"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(NormalizedEmail(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)  # chosen vertical; None -> healthcare_dental
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)  # PENDING, APPROVED, REJECTED

    @validates("email")
    def validate_email(self, key, value):
        return normalize_email(value)
