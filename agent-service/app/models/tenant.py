import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CRMType(str, enum.Enum):
    hubspot = "hubspot"
    google_sheets = "google_sheets"
    splose = "splose"
    none = "none"


class CalendarType(str, enum.Enum):
    google_calendar = "google_calendar"
    calendly = "calendly"
    none = "none"


class AccountingType(str, enum.Enum):
    xero = "xero"
    none = "none"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    twilio_phone_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    crm_type: Mapped[CRMType] = mapped_column(
        Enum(CRMType), default=CRMType.none, nullable=False
    )
    crm_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_type: Mapped[CalendarType] = mapped_column(
        Enum(CalendarType), default=CalendarType.none, nullable=False
    )
    calendar_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    twilio_account_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    twilio_auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    accounting_type: Mapped[AccountingType] = mapped_column(
        Enum(AccountingType), default=AccountingType.none, nullable=False
    )
    accounting_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    max_conversations_per_month: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
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
