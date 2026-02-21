import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.tenant import Base


class DeliveryChannel(str, enum.Enum):
    email = "email"
    slack = "slack"
    none = "none"


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Standard 5-field cron expression, e.g. "0 9 * * 1" = Mon 9am UTC
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    # The prompt sent to the agent as the "user" turn
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_channel: Mapped[DeliveryChannel] = mapped_column(
        Enum(DeliveryChannel), default=DeliveryChannel.none, nullable=False
    )
    # Email address (for email) or Slack webhook URL (for slack)
    delivery_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
