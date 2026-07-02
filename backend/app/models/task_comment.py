import uuid
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class TaskComment(BaseModel):
    __tablename__ = "task_comments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
