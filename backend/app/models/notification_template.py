from sqlalchemy import String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class NotificationTemplate(BaseModel):
    __tablename__ = "notification_templates"

    template_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    template_name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)  # email, sms, whatsapp, push
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="billing", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
