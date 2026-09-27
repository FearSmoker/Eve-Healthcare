import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebhookStatus(str, Enum):
    PROCESSED = "PROCESSED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"
    FAILED = "FAILED"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Natural idempotency key sent by payment provider
    event_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(30), default=WebhookStatus.PROCESSED.value, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
