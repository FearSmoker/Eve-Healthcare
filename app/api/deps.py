import uuid
from typing import Generator, Optional
import jwt
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ForbiddenOperationError,
    UnauthorizedAccessError,
    WebhookSignatureError,
)
from app.core.security import decode_access_token, verify_webhook_signature
from app.db.session import get_db
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate bearer JWT token and return authenticated user."""
    if not auth_credentials:
        raise UnauthorizedAccessError("Authorization header missing or invalid.")

    token = auth_credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedAccessError("Malformed token payload.")
        user_id = uuid.UUID(user_id_str)
    except UnauthorizedAccessError:
        raise  # Let our own exception propagate unchanged
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise UnauthorizedAccessError("Invalid, expired, or malformed authentication token.")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise UnauthorizedAccessError("User identified by token does not exist.")

    if not user.is_active:
        raise UnauthorizedAccessError("User account is disabled.")

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Validate that current authenticated user has ADMIN privileges."""
    if not current_user.is_admin():
        raise ForbiddenOperationError("Administrative privileges required for this action.")
    return current_user


async def verify_webhook_hmac(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
) -> None:
    """
    Optional HMAC signature verification.
    If the X-Webhook-Signature header is provided, it validates against the secret.
    """
    if x_webhook_signature:
        body_bytes = await request.body()
        if not verify_webhook_signature(body_bytes, x_webhook_signature):
            raise WebhookSignatureError("Provided HMAC webhook signature is invalid.")
