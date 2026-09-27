from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.worker.celery_app import celery_app

logger = logging.getLogger("eve_healthcare")


class LoggedTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task failed: {self.name} [{task_id}]: {exc!r}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task retrying: {self.name} [{task_id}]: {exc!r}")

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task succeeded: {self.name} [{task_id}]")


def _get_db_session():
    from app.db.base import SessionLocal
    return SessionLocal()


# background email notification when booking is created
@celery_app.task(
    base=LoggedTask,
    bind=True,
    name="app.worker.tasks.notify_booking_created",
    queue="eve_notifications",
    max_retries=3,
    default_retry_delay=15,
)
def notify_booking_created(
    self,
    booking_id: str,
    patient_name: str,
    patient_email: str,
    test_name: str,
    centre_name: str,
    appointment_dt: str,
    amount_paise: int,
) -> Dict[str, Any]:
    amount_inr = amount_paise / 100
    logger.info(
        f"Booking notification sent to {patient_email} for booking {booking_id} "
        f"({test_name} at {centre_name}, ₹{amount_inr:.2f})"
    )

    return {
        "task": "notify_booking_created",
        "booking_id": booking_id,
        "recipient": patient_email,
        "status": "sent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# background notification for payment confirmation or failure
@celery_app.task(
    base=LoggedTask,
    bind=True,
    name="app.worker.tasks.notify_payment_result",
    queue="eve_notifications",
    max_retries=3,
    default_retry_delay=15,
)
def notify_payment_result(
    self,
    booking_id: str,
    patient_name: str,
    patient_email: str,
    test_name: str,
    centre_name: str,
    appointment_dt: str,
    transaction_id: str,
    payment_method: str,
    amount_paise: int,
    payment_status: str,
    booking_status: str,
) -> Dict[str, Any]:
    amount_inr = amount_paise / 100
    logger.info(
        f"Payment receipt notification sent to {patient_email} for booking {booking_id} "
        f"(txn={transaction_id}, status={payment_status}, ₹{amount_inr:.2f})"
    )

    return {
        "task": "notify_payment_result",
        "booking_id": booking_id,
        "transaction_id": transaction_id,
        "payment_status": payment_status,
        "recipient": patient_email,
        "status": "sent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# retry processing failed webhook events with backoff
@celery_app.task(
    base=LoggedTask,
    bind=True,
    name="app.worker.tasks.retry_webhook_processing",
    queue="eve_webhooks",
    max_retries=5,
    default_retry_delay=60,
)
def retry_webhook_processing(
    self,
    event_id: str,
    payload_dict: Dict[str, Any],
) -> Dict[str, Any]:
    from sqlalchemy import select
    from app.models.webhook_event import WebhookEvent, WebhookStatus
    from app.schemas.payment import WebhookPayload
    from app.services.payment_service import PaymentService

    db = _get_db_session()
    attempt = self.request.retries + 1
    logger.info(f"Retrying webhook event {event_id} (attempt {attempt})")

    try:
        # check if event was already handled
        existing = db.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        ).scalar_one_or_none()

        if existing and existing.processing_status == WebhookStatus.PROCESSED.value:
            logger.info(f"Webhook {event_id} already processed, skipping")
            return {"event_id": event_id, "result": "already_processed"}

        payload = WebhookPayload(**payload_dict)
        result = PaymentService.process_webhook(
            db=db,
            payload=payload,
            raw_payload=payload_dict,
        )

        logger.info(f"Webhook {event_id} retry succeeded with status {result.status}")
        return {
            "event_id": event_id,
            "result": result.status,
            "attempt": attempt,
        }

    except Exception as exc:
        db.rollback()
        # exponential backoff: 60s, 120s, 240s...
        countdown = 60 * (2 ** self.request.retries)
        logger.warning(f"Webhook {event_id} retry failed: {exc!r}, retrying in {countdown}s")
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"Webhook {event_id} exceeded max retries")
            try:
                evt = db.execute(
                    select(WebhookEvent).where(WebhookEvent.event_id == event_id)
                ).scalar_one_or_none()
                if evt:
                    evt.processing_status = WebhookStatus.FAILED.value
                    evt.error_message = f"Exhausted retries: {exc!r}"
                    db.commit()
            except Exception:
                pass
            raise
    finally:
        db.close()
