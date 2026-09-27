from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import EntityAlreadyExistsError, InvalidCredentialsError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserLoginRequest, UserResponse, UserSignUpRequest
from app.config import settings


class AuthService:
    @staticmethod
    def signup(db: Session, request: UserSignUpRequest) -> User:
        existing_user = db.execute(
            select(User).where(User.email == request.email)
        ).scalar_one_or_none()

        if existing_user:
            raise EntityAlreadyExistsError("User", "email", request.email)

        # public signup always defaults to patient
        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
            phone=request.phone,
            role=UserRole.PATIENT.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate(db: Session, request: UserLoginRequest) -> User:
        user = db.execute(
            select(User).where(User.email == request.email)
        ).scalar_one_or_none()

        # verify password to prevent user enumeration
        password_ok = verify_password(request.password, user.password_hash) if user else False

        if not user or not password_ok:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError("User account is inactive. Please contact support.")

        return user

    @classmethod
    def create_token_for_user(cls, user: User) -> TokenResponse:
        token = create_access_token(
            subject=str(user.id),
            role=user.role,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
