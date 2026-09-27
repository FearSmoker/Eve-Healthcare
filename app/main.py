import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app import __version__
from app.api.v1.payments import router as payments_root_router
from app.api.v1.router import api_v1_router
from app.config import settings
from app.core.exceptions import AppException
from app.core.limiter import limiter
from app.core.logging import logger
from app.db.base import Base, engine
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info(f"{settings.PROJECT_NAME} initialized successfully.")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description="EVE Healthcare diagnostic test booking & payment service",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# rate limiter configuration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# cors configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)


# Correlation ID, Timing & Security Headers Middleware
@app.middleware("http")
async def security_and_correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    # Correlation and timing headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)

    # Security headers — prevent clickjacking, MIME sniffing, etc.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    logger.info(
        f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)"
    )
    return response


# Standardized Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions with structured error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors with clear formatting."""
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        errors.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "; ".join(errors),
            "error_code": "VALIDATION_ERROR",
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unexpected server exceptions."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
    )


# Health Check
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check verifying service, database & Redis connectivity",
)
def health_check() -> HealthResponse:
    """Check API, database, and Redis cache status."""
    from app.core.cache import is_redis_available

    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check DB ping failed: {e}")
        db_status = "error"

    if not settings.CACHE_ENABLED:
        redis_status = "disabled"
    elif is_redis_available():
        redis_status = "connected"
    else:
        redis_status = "unavailable"

    overall_ok = db_status == "connected"

    return HealthResponse(
        status="ok" if overall_ok else "degraded",
        database=db_status,
        redis=redis_status,
        cache_enabled=settings.CACHE_ENABLED,
        environment=settings.ENVIRONMENT,
        version=__version__,
    )


# api routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
app.include_router(payments_root_router)

# serve frontend spa
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
