import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.centre import CentreTest
    from app.models.payment import Payment
    from app.models.user import User


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("centre_tests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appointment_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Price snapshotted at time of booking (in paise)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=BookingStatus.PENDING.value, nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    centre_test: Mapped["CentreTest"] = relationship(
        "CentreTest", back_populates="bookings"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="booking", cascade="all, delete-orphan"
    )
