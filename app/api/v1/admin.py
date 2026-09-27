import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.exceptions import AppException, EntityNotFoundError
from app.core.logging import logger
from app.models.user import User
from app.models.webhook_event import WebhookEvent, WebhookStatus

router = APIRouter(prefix="/admin", tags=["Admin"])


class WebhookRetryResponse(BaseModel):
    event_id: str
    task_id: str
    message: str


@router.post(
    "/webhooks/{event_id}/retry",
    response_model=WebhookRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a failed webhook event for background retry",
)
def retry_failed_webhook(
    event_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> WebhookRetryResponse:
    # check webhook event exists
    event = db.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    ).scalar_one_or_none()

    if not event:
        raise EntityNotFoundError("WebhookEvent", event_id)

    # do not retry already completed events
    if event.processing_status == WebhookStatus.PROCESSED.value:
        raise AppException(
            status_code=409,
            detail="This webhook event has already been successfully processed.",
            error_code="WEBHOOK_ALREADY_PROCESSED",
        )

    # enqueue task for background retry
    try:
        from app.worker.tasks import retry_webhook_processing
        result = retry_webhook_processing.delay(
            event_id=event.event_id,
            payload_dict=event.raw_payload,
        )
        task_id = result.id
        logger.info(f"Webhook retry queued: event_id={event_id} task_id={task_id}")
    except Exception as exc:
        logger.error(f"Failed to enqueue webhook retry for {event_id}: {exc}")
        raise AppException(
            status_code=503,
            detail="Celery broker is unavailable — could not enqueue the retry task.",
            error_code="CELERY_BROKER_UNAVAILABLE",
        )

    return WebhookRetryResponse(
        event_id=event_id,
        task_id=task_id,
        message=f"Webhook event '{event_id}' has been queued for retry.",
    )
