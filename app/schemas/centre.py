import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class DiagnosticTestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50, description="Unique test code (e.g. CBC, LFT)")
    category: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    preparation_instructions: Optional[str] = None


class DiagnosticTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    category: str
    description: Optional[str] = None
    preparation_instructions: Optional[str] = None
    is_active: bool
    created_at: datetime


class CentreTestLinkCreate(BaseModel):
    test_id: uuid.UUID
    price_paise: int = Field(..., gt=0, description="Test price in paise (e.g. 50000 paise = ₹500.00)")
    is_available: bool = True


class CentreTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    test: DiagnosticTestResponse
    price_paise: int
    is_available: bool

    @computed_field
    @property
    def price_inr(self) -> float:
        """Convenience property displaying amount in INR."""
        return round(self.price_paise / 100.0, 2)


class DiagnosticCentreCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=5, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: str = Field(..., min_length=4, max_length=20)
    contact_phone: Optional[str] = Field(None, max_length=30)


class DiagnosticCentreListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    city: str
    state: Optional[str] = None
    pincode: str
    contact_phone: Optional[str] = None
    is_active: bool
    created_at: datetime


class DiagnosticCentreDetailResponse(DiagnosticCentreListResponse):
    centre_tests: List[CentreTestResponse] = []
