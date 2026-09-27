import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from app.config import settings
from app.models.user import User
from app.schemas.centre import (
    CentreTestLinkCreate,
    CentreTestResponse,
    DiagnosticCentreCreate,
    DiagnosticCentreDetailResponse,
    DiagnosticCentreListResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.centre_service import CentreService

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


def _list_key(city: Optional[str], search: Optional[str], page: int, page_size: int) -> str:
    return f"eve:centres:list:{city or ''}:{search or ''}:{page}:{page_size}"


def _detail_key(centre_id: uuid.UUID) -> str:
    return f"eve:centres:detail:{centre_id}"


@router.get(
    "",
    response_model=PaginatedResponse[DiagnosticCentreListResponse],
    status_code=status.HTTP_200_OK,
    summary="List diagnostic centres with filtering and pagination",
)
def list_centres(
    city: Optional[str] = Query(None, description="Filter centres by city name"),
    search: Optional[str] = Query(None, description="Search by centre name or address"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DiagnosticCentreListResponse]:
    # check redis cache
    cache_key = _list_key(city, search, page, page_size)
    cached = cache_get(cache_key)
    if cached:
        return PaginatedResponse[DiagnosticCentreListResponse](**cached)

    items, total = CentreService.list_centres(
        db, city=city, search=search, page=page, page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    response = PaginatedResponse(
        items=[DiagnosticCentreListResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    # cache for 5 minutes
    cache_set(cache_key, response.model_dump(mode="json"), ttl=settings.CACHE_TTL_CENTRES_LIST)
    return response


@router.get(
    "/{id}",
    response_model=DiagnosticCentreDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get centre details with available tests and prices",
)
def get_centre_detail(
    id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DiagnosticCentreDetailResponse:
    # check redis cache
    cache_key = _detail_key(id)
    cached = cache_get(cache_key)
    if cached:
        return DiagnosticCentreDetailResponse(**cached)

    centre = CentreService.get_centre_by_id(db, id)
    response = DiagnosticCentreDetailResponse.model_validate(centre)
    # cache for 10 minutes
    cache_set(cache_key, response.model_dump(mode="json"), ttl=settings.CACHE_TTL_CENTRE_DETAIL)
    return response


@router.post(
    "",
    response_model=DiagnosticCentreListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic centre (Admin only)",
)
def create_centre(
    request: DiagnosticCentreCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> DiagnosticCentreListResponse:
    centre = CentreService.create_centre(db, request)
    # invalidate centres list cache
    cache_delete_pattern("eve:centres:list:*")
    return DiagnosticCentreListResponse.model_validate(centre)


@router.post(
    "/{id}/tests",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a diagnostic test to a centre with pricing (Admin only)",
)
def link_test_to_centre(
    id: uuid.UUID,
    request: CentreTestLinkCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> CentreTestResponse:
    link = CentreService.link_test_to_centre(db, id, request)
    # purge centre detail and list cache
    cache_delete(_detail_key(id))
    cache_delete_pattern("eve:centres:list:*")
    return CentreTestResponse.model_validate(link)
