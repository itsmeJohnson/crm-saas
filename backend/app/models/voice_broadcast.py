import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class VoiceBroadcast(BaseModel):
    """An outbound bulk voice broadcast job (OBD voice note or TTS).

    A broadcast targets a list of numbers with either a pre-recorded voice media
    (``mode='voice_note'``, referencing the vendor ``voice_medias_id``) or a
    text-to-speech script (``mode='tts'``). Per-number delivery is tracked in
    :class:`VoiceBroadcastRecipient`. Org-scoped; the vendor account is the org's
    BulkSMSPlans SMS credentials.
    """
    __tablename__ = "voice_broadcasts"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # voice_note|tts
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft|queued|sent|scheduled|failed

    # voice_note mode
    voice_type: Mapped[str | None] = mapped_column(String(8), nullable=True)  # 37 IVR / 34 promo-30 / 33 txn-30 / 35 TTS
    voice_medias_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # tts mode
    tts_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tts_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # scheduling / retry
    scheduled: Mapped[bool] = mapped_column(default=False, nullable=False)
    scheduled_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    provider: Mapped[str] = mapped_column(String(30), default="bulksmsplans", nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipients: Mapped[list["VoiceBroadcastRecipient"]] = relationship(
        back_populates="broadcast", cascade="all, delete-orphan")


class VoiceBroadcastRecipient(BaseModel):
    """Per-number delivery record for a voice broadcast; updated from voice DLR."""
    __tablename__ = "voice_broadcast_recipients"
    __table_args__ = (
        Index("ix_voice_recipients_broadcast", "broadcast_id"),
        Index("ix_voice_recipients_unique", "unique_id"),
    )

    broadcast_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_broadcasts.id"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    unique_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    vendor_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dtmf: Mapped[str | None] = mapped_column(String(20), nullable=True)
    call_duration: Mapped[str | None] = mapped_column(String(20), nullable=True)

    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)

    broadcast: Mapped["VoiceBroadcast"] = relationship(back_populates="recipients")
