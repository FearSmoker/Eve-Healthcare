from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    detail: str
    error_code: str
    status_code: int


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str
    version: str
    redis: Optional[str] = None   # "connected" | "unavailable" | "disabled"
    cache_enabled: bool = False
