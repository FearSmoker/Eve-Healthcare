import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    EntityNotFoundError,
    ForbiddenOperationError,
    InvalidBookingError,
    InvalidStateTransitionError,
)
from app.models.booking import Booking, BookingStatus
from app.models.centre import CentreTest
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreateRequest


class BookingService:
    @staticmethod
    def create_booking(
        db: Session, current_user: User, request: BookingCreateRequest
    ) -> Booking:
        # verify centre test offering exists
        centre_test_stmt = (
            select(CentreTest)
            .options(
                selectinload(CentreTest.centre),
                selectinload(CentreTest.test),
            )
            .where(CentreTest.id == request.centre_test_id)
        )
        centre_test = db.execute(centre_test_stmt).scalar_one_or_none()
        if not centre_test:
            raise EntityNotFoundError("Diagnostic Test Offering", request.centre_test_id)

        if not centre_test.is_available:
            raise InvalidBookingError(
                "This diagnostic test is currently unavailable at the selected centre.",
                error_code="TEST_OFFERING_UNAVAILABLE",
            )

        if not centre_test.centre.is_active or not centre_test.test.is_active:
            raise InvalidBookingError(
                "The requested centre or test is not currently active.",
                error_code="CENTRE_OR_TEST_INACTIVE",
            )

        # freeze price at booking creation
        snapshotted_price_paise = centre_test.price_paise

        booking = Booking(
            user_id=current_user.id,
            centre_test_id=centre_test.id,
            appointment_datetime=request.appointment_datetime,
            amount_paise=snapshotted_price_paise,
            status=BookingStatus.PENDING.value,
            notes=request.notes,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        # reload with eager relationships
        loaded_booking = db.execute(
            select(Booking)
            .options(
                selectinload(Booking.centre_test).selectinload(CentreTest.centre),
                selectinload(Booking.centre_test).selectinload(CentreTest.test),
                selectinload(Booking.user),
            )
            .where(Booking.id == booking.id)
        ).scalar_one()

        # queue background notification
        BookingService._dispatch_booking_notification(loaded_booking)

        return loaded_booking

    @staticmethod
    def _dispatch_booking_notification(booking) -> None:
        try:
            from app.worker.tasks import notify_booking_created
            notify_booking_created.delay(
                booking_id=str(booking.id),
                patient_name=booking.user.full_name if hasattr(booking, "user") and booking.user else "Patient",
                patient_email=booking.user.email if hasattr(booking, "user") and booking.user else "patient@example.com",
                test_name=booking.centre_test.test.name,
                centre_name=booking.centre_test.centre.name,
                appointment_dt=booking.appointment_datetime.isoformat(),
                amount_paise=booking.amount_paise,
            )
        except Exception as e:
            # ignore if celery broker is offline
            import logging
            logging.getLogger("eve_healthcare").warning(
                f"Could not dispatch notify_booking_created for booking {booking.id}: {e}"
            )

    @staticmethod
    def get_booking_by_id(
        db: Session, booking_id: uuid.UUID, current_user: User
    ) -> Booking:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.centre_test).selectinload(CentreTest.centre),
                selectinload(Booking.centre_test).selectinload(CentreTest.test),
            )
            .where(Booking.id == booking_id)
        )
        booking = db.execute(stmt).scalar_one_or_none()
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        # patient can only access their own bookings
        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise ForbiddenOperationError("You are not authorized to view this booking.")

        return booking

    @staticmethod
    def list_bookings(
        db: Session,
        current_user: User,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[Sequence[Booking], int]:
        query = select(Booking).options(
            selectinload(Booking.centre_test).selectinload(CentreTest.centre),
            selectinload(Booking.centre_test).selectinload(CentreTest.test),
        )

        # filter by patient unless admin
        if current_user.role != UserRole.ADMIN.value:
            query = query.where(Booking.user_id == current_user.id)

        if status_filter:
            query = query.where(Booking.status == status_filter.upper())

        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.execute(count_stmt).scalar_one()

        offset = (page - 1) * page_size
        items = db.execute(
            query.order_by(Booking.created_at.desc()).offset(offset).limit(page_size)
        ).scalars().all()

        return items, total

    @staticmethod
    def cancel_booking(
        db: Session, booking_id: uuid.UUID, current_user: User
    ) -> Booking:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.centre_test).selectinload(CentreTest.centre),
                selectinload(Booking.centre_test).selectinload(CentreTest.test),
            )
            .where(Booking.id == booking_id)
        )
        booking = db.execute(stmt).scalar_one_or_none()
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise ForbiddenOperationError("You are not authorized to cancel this booking.")

        # disallow cancelling already finished states
        if booking.status == BookingStatus.CANCELLED.value:
            raise InvalidStateTransitionError(
                current_state=booking.status,
                attempted_state=BookingStatus.CANCELLED.value,
                reason="This booking has already been cancelled.",
            )

        if booking.status == BookingStatus.FAILED.value:
            raise InvalidStateTransitionError(
                current_state=booking.status,
                attempted_state=BookingStatus.CANCELLED.value,
                reason="Failed bookings cannot be cancelled.",
            )

        # disallow cancelling past appointments
        if booking.status == BookingStatus.CONFIRMED.value:
            now = datetime.now(timezone.utc)
            apt_time = (
                booking.appointment_datetime
                if booking.appointment_datetime.tzinfo
                else booking.appointment_datetime.replace(tzinfo=timezone.utc)
            )
            if apt_time <= now:
                raise InvalidStateTransitionError(
                    current_state=booking.status,
                    attempted_state=BookingStatus.CANCELLED.value,
                    reason="Cannot cancel a booking whose appointment time has already passed.",
                )

        booking.status = BookingStatus.CANCELLED.value
        db.commit()
        db.refresh(booking)
        return booking
