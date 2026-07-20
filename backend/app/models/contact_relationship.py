import uuid
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ContactRelationship(BaseModel):
    """A directed relationship between two contacts, e.g. contact -> reports_to -> other."""
    __tablename__ = "contact_relationships"
    __table_args__ = (
        UniqueConstraint("contact_id", "related_contact_id", "relationship_type", name="uq_contact_rel"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    related_contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)  # reports_to|manager_of|colleague|assistant|other
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
