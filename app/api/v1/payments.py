from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_webhook_hmac
from app.models.user import User
from app.schemas.payment import (
    PaymentResponse,
    PaymentSimulateRequest,
    WebhookPayload,
    WebhookResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate payment for a booking",
)
@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def simulate_payment(
    request: PaymentSimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentResponse:
    # process payment and update booking status
    return PaymentService.process_simulated_payment(db, current_user, request)


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Idempotent payment webhook endpoint",
    dependencies=[Depends(verify_webhook_hmac)],
)
@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(verify_webhook_hmac)],
)
async def payment_webhook(
    request: Request,
    payload: WebhookPayload,
    db: Session = Depends(get_db),
) -> WebhookResponse:
    # idempotent webhook processing with duplicate protection
    raw_json = await request.json()
    return PaymentService.process_webhook(db, payload, raw_json)
