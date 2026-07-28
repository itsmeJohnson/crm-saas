import uuid
from sqlalchemy import String, ForeignKey, Boolean, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class TelephonySettings(BaseModel):
    """Per-organization telephony/calling provider configuration (one row per org).

    Credentials are managed ONLY at the organization level by the Super Admin
    (or an OrgAdmin granted ``manage_integrations``); employees never see or set
    them. The four secret fields are stored AES-256-GCM encrypted (see
    ``app.core.crypto``) and are decrypted only server-side when calling the
    provider — they are never serialised to any API response.
    """
    __tablename__ = "telephony_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_telephony_settings_organization"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="myoperator", nullable=False)  # myoperator|knowlarity
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Non-secret configuration ----
    company_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    public_ivr_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    call_type: Mapped[str] = mapped_column(String(8), default="1", nullable=False)  # MyOperator OBD type 1|2|3
    user_uuid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_caller_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    std_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ---- Secrets (AES-256-GCM ciphertext at rest; never returned to clients) ----
    authentication_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    x_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Feature toggles ----
    call_recording: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    power_dialer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    predictive_dialer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_assignment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Dialing policy ----
    call_retry_count: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    retry_interval_seconds: Mapped[int] = mapped_column(Integer, default=7200, nullable=False)  # 2h
    max_call_duration_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
