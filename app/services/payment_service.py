import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AppException,
    EntityNotFoundError,
    ForbiddenOperationError,
    InvalidStateTransitionError,
)
from app.core.logging import logger
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.schemas.payment import (
    PaymentResponse,
    PaymentSimulateRequest,
    WebhookPayload,
    WebhookResponse,
)


class PaymentService:
    @staticmethod
    def process_simulated_payment(
        db: Session, current_user: User, request: PaymentSimulateRequest
    ) -> PaymentResponse:
        # lock booking row during payment processing
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.centre_test),
                selectinload(Booking.user),
            )
            .where(Booking.id == request.booking_id)
            .with_for_update()
        )
        booking = db.execute(stmt).scalar_one_or_none()
        if not booking:
            raise EntityNotFoundError("Booking", request.booking_id)

        # verify booking belongs to current user
        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise ForbiddenOperationError("You are not authorized to pay for this booking.")

        # disallow paying for already settled or cancelled bookings
        if booking.status == BookingStatus.CONFIRMED.value:
            raise AppException(
                status_code=409,
                detail="This booking has already been paid for and confirmed.",
                error_code="BOOKING_ALREADY_PAID",
            )

        if booking.status == BookingStatus.CANCELLED.value:
            raise InvalidStateTransitionError(
                current_state=booking.status,
                attempted_state=BookingStatus.CONFIRMED.value,
                reason="Cannot process payment for a cancelled booking.",
            )

        if booking.status == BookingStatus.FAILED.value:
            raise InvalidStateTransitionError(
                current_state=booking.status,
                attempted_state=BookingStatus.CONFIRMED.value,
                reason="Booking payment previously failed. Please create a new booking.",
            )

        # evaluate simulated payment outcome
        is_success = not request.simulate_failure
        outcome_status = PaymentStatus.SUCCESS.value if is_success else PaymentStatus.FAILED.value
        updated_booking_status = (
            BookingStatus.CONFIRMED.value if is_success else BookingStatus.FAILED.value
        )

        booking.status = updated_booking_status

        # record transaction
        transaction_id = f"txn_sim_{uuid.uuid4().hex[:16]}"
        payment = Payment(
            booking_id=booking.id,
            transaction_id=transaction_id,
            amount_paise=booking.amount_paise,
            status=outcome_status,
            payment_method=request.payment_method or "SIMULATED_CARD",
            provider_reference=f"prov_{uuid.uuid4().hex[:12]}",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        logger.info(
            f"Payment processed: booking={booking.id}, status={outcome_status}, txn={transaction_id}"
        )

        # queue notification task
        PaymentService._dispatch_payment_notification(
            booking=booking,
            transaction_id=transaction_id,
            payment_method=request.payment_method or "SIMULATED_CARD",
            amount_paise=payment.amount_paise,
            payment_status=outcome_status,
            booking_status=booking.status,
        )

        return PaymentResponse(
            id=payment.id,
            booking_id=payment.booking_id,
            transaction_id=payment.transaction_id,
            amount_paise=payment.amount_paise,
            status=payment.status,
            payment_method=payment.payment_method,
            provider_reference=payment.provider_reference,
            created_at=payment.created_at,
            booking_status=booking.status,
        )

    @staticmethod
    def _dispatch_payment_notification(
        booking,
        transaction_id: str,
        payment_method: str,
        amount_paise: int,
        payment_status: str,
        booking_status: str,
    ) -> None:
        try:
            from app.worker.tasks import notify_payment_result
            user = booking.user if hasattr(booking, "user") and booking.user else None
            centre_test = booking.centre_test if hasattr(booking, "centre_test") and booking.centre_test else None

            notify_payment_result.delay(
                booking_id=str(booking.id),
                patient_name=user.full_name if user else "Patient",
                patient_email=user.email if user else "patient@example.com",
                test_name=centre_test.test.name if centre_test and centre_test.test else "Diagnostic Test",
                centre_name=centre_test.centre.name if centre_test and centre_test.centre else "Diagnostic Centre",
                appointment_dt=booking.appointment_datetime.isoformat(),
                transaction_id=transaction_id,
                payment_method=payment_method,
                amount_paise=amount_paise,
                payment_status=payment_status,
                booking_status=booking_status,
            )
        except Exception as e:
            # ignore if celery broker is offline
            logger.warning(f"Could not dispatch payment notification for {booking.id}: {e}")

    @staticmethod
    def process_webhook(
        db: Session,
        payload: WebhookPayload,
        raw_payload: Dict[str, Any],
    ) -> WebhookResponse:
        # check idempotency key
        existing_event = db.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == payload.event_id)
        ).scalar_one_or_none()

        if existing_event:
            logger.info(f"Duplicate webhook event {payload.event_id} skipped")
            return WebhookResponse(
                status="already_processed",
                event_id=payload.event_id,
                booking_id=payload.booking_id,
                message="Event has already been processed previously. Acknowledging with no side-effects.",
            )

        # save event to audit log
        webhook_event = WebhookEvent(
            event_id=payload.event_id,
            event_type=payload.event_type,
            booking_id=payload.booking_id,
            raw_payload=raw_payload,
            processing_status=WebhookStatus.PROCESSED.value,
        )
        db.add(webhook_event)

        try:
            db.flush()
        except IntegrityError:
            # handle race condition on duplicate event insert
            db.rollback()
            return WebhookResponse(
                status="already_processed",
                event_id=payload.event_id,
                booking_id=payload.booking_id,
                message="Concurrent event deduplicated via atomic constraint.",
            )

        # fetch booking with row lock
        stmt = (
            select(Booking)
            .where(Booking.id == payload.booking_id)
            .with_for_update()
        )
        booking = db.execute(stmt).scalar_one_or_none()

        if not booking:
            webhook_event.processing_status = WebhookStatus.FAILED.value
            webhook_event.error_message = f"Booking with ID '{payload.booking_id}' not found."
            db.commit()
            raise EntityNotFoundError("Booking", payload.booking_id)

        # update booking state based on event
        if payload.event_type == "payment.succeeded":
            if booking.status == BookingStatus.PENDING.value:
                booking.status = BookingStatus.CONFIRMED.value
                payment = Payment(
                    booking_id=booking.id,
                    transaction_id=f"txn_wh_{payload.event_id}",
                    amount_paise=booking.amount_paise,
                    status=PaymentStatus.SUCCESS.value,
                    payment_method="WEBHOOK_EXTERNAL",
                    provider_reference=payload.provider_reference,
                )
                db.add(payment)

        elif payload.event_type == "payment.failed":
            if booking.status == BookingStatus.PENDING.value:
                booking.status = BookingStatus.FAILED.value
                payment = Payment(
                    booking_id=booking.id,
                    transaction_id=f"txn_wh_{payload.event_id}",
                    amount_paise=booking.amount_paise,
                    status=PaymentStatus.FAILED.value,
                    payment_method="WEBHOOK_EXTERNAL",
                    provider_reference=payload.provider_reference,
                )
                db.add(payment)

        webhook_event.processed_at = datetime.now(timezone.utc)
        db.commit()

        return WebhookResponse(
            status="processed",
            event_id=payload.event_id,
            booking_id=payload.booking_id,
            message="Webhook event processed and booking state updated.",
        )
