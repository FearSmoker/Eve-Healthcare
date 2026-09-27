import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class BookingCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    centre_test_id: uuid.UUID = Field(
        ..., description="ID of the specific diagnostic test offering at a chosen centre"
    )
    appointment_datetime: datetime = Field(
        ..., description="Scheduled appointment datetime (must be in the future)"
    )
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("appointment_datetime")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        # Normalize timezone if naive
        now = datetime.now(timezone.utc)
        target = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if target <= now:
            raise ValueError("Appointment datetime must be in the future.")
        return target


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    centre_test_id: uuid.UUID
    appointment_datetime: datetime
    amount_paise: int
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Additional contextual fields populated from relationships
    centre_name: Optional[str] = None
    test_name: Optional[str] = None

    @computed_field
    @property
    def amount_inr(self) -> float:
        """Formatted amount in Indian Rupees."""
        return round(self.amount_paise / 100.0, 2)


class BookingCancelResponse(BaseModel):
    id: uuid.UUID
    status: str
    message: str
