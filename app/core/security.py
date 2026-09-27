import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    role: str = "PATIENT",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def generate_webhook_signature(payload_bytes: bytes) -> str:
    """Generate HMAC-SHA256 signature for simulated webhook testing."""
    return hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify HMAC-SHA256 webhook signature against configured secret."""
    expected_signature = generate_webhook_signature(payload_bytes)
    return hmac.compare_digest(expected_signature, signature_header)
