import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Activity(BaseModel):
    __tablename__ = "activities"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. Call, Meeting, Email, Task
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Planned", nullable=False) # e.g. Planned, Completed, Overdue
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    
    # Optional references
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Call recording & integration fields
    call_sid: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    recording_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    call_duration: Mapped[int | None] = mapped_column(nullable=True)
    call_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Communication attachments (reused for the Communication Center; INBOUND/OUTBOUND direction reuses call_direction)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of {filename, url, size, uploaded_by, uploaded_at}
    # Calling platform: free-form tags on Call activities + the structured disposition
    # outcome (mirrors CallDispositionStatus values; the human-readable copy stays in subject/description)
    call_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of strings
    call_disposition: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # SMS delivery lifecycle (activity_type='SMS'): provider status + retry bookkeeping.
    # Direction reuses call_direction (INBOUND/OUTBOUND), the same field the Comm Center uses.
    sms_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # queued|sent|delivered|failed|undelivered|received
    sms_provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sms_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sms_retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    sms_segments: Mapped[int | None] = mapped_column(nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # WhatsApp lifecycle (activity_type='WhatsApp'): reuses to_number/from_number,
    # attachments (media), call_direction. wa_status adds a 'read' state SMS lacks.
    wa_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # sent|delivered|read|failed|received
    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    wa_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wa_media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # text|image|video|document|audio
    wa_template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wa_conversation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    # Email lifecycle (activity_type='Email'): threading + open/click tracking + drafts.
    # Reuses subject, description (HTML body), attachments, call_direction.
    email_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # RFC Message-ID
    email_thread_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    email_in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_from: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_to: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email_cc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # draft|sent|failed|received
    email_open_count: Mapped[int] = mapped_column(default=0, nullable=False)
    email_click_count: Mapped[int] = mapped_column(default=0, nullable=False)
    email_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_draft: Mapped[bool] = mapped_column(default=False, nullable=False)
    email_tracking_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
