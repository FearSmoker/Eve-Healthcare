from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserResponse,
    UserSignUpRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient account",
)
@limiter.limit("5/minute")
def signup(
    request: Request,
    body: UserSignUpRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    # register patient account
    user = AuthService.signup(db, body)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login with JWT generation",
)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    # authenticate and issue jwt
    user = AuthService.authenticate(db, body)
    return AuthService.create_token_for_user(user)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_current_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve profile details of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
