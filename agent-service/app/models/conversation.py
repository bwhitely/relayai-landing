import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.tenant import Base


class ChannelType(str, enum.Enum):
    whatsapp = "whatsapp"
    web = "web"
    sms = "sms"
    facebook = "facebook"
    instagram = "instagram"


class ConversationStatus(str, enum.Enum):
    active = "active"
    escalated = "escalated"
    closed = "closed"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_tenant_external", "tenant_id", "external_identifier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    external_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType), nullable=False
    )
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.active, nullable=False
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
