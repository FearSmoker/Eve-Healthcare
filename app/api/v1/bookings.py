import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import (
    BookingCancelResponse,
    BookingCreateRequest,
    BookingResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _to_booking_response(b: Booking) -> BookingResponse:
    centre_name = None
    test_name = None
    if b.centre_test:
        if b.centre_test.centre:
            centre_name = b.centre_test.centre.name
        if b.centre_test.test:
            test_name = b.centre_test.test.name

    return BookingResponse(
        id=b.id,
        user_id=b.user_id,
        centre_test_id=b.centre_test_id,
        appointment_datetime=b.appointment_datetime,
        amount_paise=b.amount_paise,
        status=b.status,
        notes=b.notes,
        created_at=b.created_at,
        updated_at=b.updated_at,
        centre_name=centre_name,
        test_name=test_name,
    )


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test booking",
)
def create_booking(
    request: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    booking = BookingService.create_booking(db, current_user, request)
    return _to_booking_response(booking)


@router.get(
    "",
    response_model=PaginatedResponse[BookingResponse],
    status_code=status.HTTP_200_OK,
    summary="List bookings for the authenticated user",
)
def list_bookings(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[BookingResponse]:
    items, total = BookingService.list_bookings(
        db, current_user, status_filter=status_filter, page=page, page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return PaginatedResponse(
        items=[_to_booking_response(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get booking details by ID",
)
def get_booking(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    booking = BookingService.get_booking_by_id(db, id, current_user)
    return _to_booking_response(booking)


@router.post(
    "/{id}/cancel",
    response_model=BookingCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending or confirmed booking",
)
def cancel_booking(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingCancelResponse:
    booking = BookingService.cancel_booking(db, id, current_user)
    return BookingCancelResponse(
        id=booking.id,
        status=booking.status,
        message="Booking cancelled successfully.",
    )
