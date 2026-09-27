import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.core.cache import cache_delete_pattern, cache_get, cache_set
from app.config import settings
from app.models.user import User
from app.schemas.centre import DiagnosticTestCreate, DiagnosticTestResponse
from app.schemas.common import PaginatedResponse
from app.services.centre_service import CentreService

router = APIRouter(prefix="/tests", tags=["Diagnostic Tests"])


def _list_key(category: Optional[str], search: Optional[str], page: int, page_size: int) -> str:
    return f"eve:tests:list:{category or ''}:{search or ''}:{page}:{page_size}"


@router.get(
    "",
    response_model=PaginatedResponse[DiagnosticTestResponse],
    status_code=status.HTTP_200_OK,
    summary="List diagnostic tests with category filtering and search",
)
def list_tests(
    category: Optional[str] = Query(None, description="Filter by test category"),
    search: Optional[str] = Query(None, description="Search by test name or code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DiagnosticTestResponse]:
    # check redis cache
    cache_key = _list_key(category, search, page, page_size)
    cached = cache_get(cache_key)
    if cached:
        return PaginatedResponse[DiagnosticTestResponse](**cached)

    items, total = CentreService.list_tests(
        db, category=category, search=search, page=page, page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    response = PaginatedResponse(
        items=[DiagnosticTestResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    # cache for 10 minutes
    cache_set(cache_key, response.model_dump(mode="json"), ttl=settings.CACHE_TTL_TESTS_LIST)
    return response


@router.post(
    "",
    response_model=DiagnosticTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test definition (Admin only)",
)
def create_test(
    request: DiagnosticTestCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> DiagnosticTestResponse:
    test = CentreService.create_test(db, request)
    # purge test list cache
    cache_delete_pattern("eve:tests:list:*")
    return DiagnosticTestResponse.model_validate(test)
