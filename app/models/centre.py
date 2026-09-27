import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.booking import Booking


class DiagnosticCentre(Base):
    __tablename__ = "diagnostic_centres"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    centre_tests: Mapped[List["CentreTest"]] = relationship(
        "CentreTest", back_populates="centre", cascade="all, delete-orphan"
    )


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    preparation_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    centre_tests: Mapped[List["CentreTest"]] = relationship(
        "CentreTest", back_populates="test", cascade="all, delete-orphan"
    )


class CentreTest(Base):
    __tablename__ = "centre_tests"
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
        CheckConstraint("price_paise > 0", name="chk_price_paise_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diagnostic_centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Stored as integer paise (e.g. ₹500.00 -> 50000 paise) to prevent floating point inaccuracies
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    centre: Mapped["DiagnosticCentre"] = relationship(
        "DiagnosticCentre", back_populates="centre_tests"
    )
    test: Mapped["DiagnosticTest"] = relationship(
        "DiagnosticTest", back_populates="centre_tests"
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking", back_populates="centre_test"
    )
