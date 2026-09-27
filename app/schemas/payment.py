import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class PaymentSimulateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    booking_id: uuid.UUID
    payment_method: str = Field(
        default="SIMULATED_CARD",
        max_length=50,
        pattern=r"^[A-Z0-9_]+$",
        description="Payment method identifier (e.g. UPI, CREDIT_CARD, SIMULATED_CARD)",
    )
    simulate_failure: bool = Field(
        default=False,
        description="Explicitly simulate a payment failure for testing purposes",
    )


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    transaction_id: str
    amount_paise: int
    status: str
    payment_method: str
    provider_reference: Optional[str] = None
    created_at: datetime
    booking_status: str

    @computed_field
    @property
    def amount_inr(self) -> float:
        return round(self.amount_paise / 100.0, 2)


class WebhookPayload(BaseModel):
    event_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique event identifier from payment provider",
    )
    event_type: str = Field(
        ...,
        description="Event type: 'payment.succeeded' or 'payment.failed'",
        pattern=r"^payment\.(succeeded|failed)$",
    )
    booking_id: uuid.UUID
    amount_paise: int = Field(..., gt=0)
    provider_reference: Optional[str] = Field(None, max_length=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookResponse(BaseModel):
    status: str = Field(..., description="'processed' or 'already_processed'")
    event_id: str
    booking_id: Optional[uuid.UUID] = None
    message: str
