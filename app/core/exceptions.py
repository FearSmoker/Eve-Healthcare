from typing import Any, Optional
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception with standardized error_code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        extra: Optional[dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}


class EntityNotFoundError(AppException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} with identifier '{identifier}' was not found.",
            error_code=f"{entity_name.upper().replace(' ', '_')}_NOT_FOUND",
        )


class EntityAlreadyExistsError(AppException):
    def __init__(self, entity_name: str, field: str, value: Any):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{entity_name} with {field} '{value}' already exists.",
            error_code=f"{entity_name.upper().replace(' ', '_')}_ALREADY_EXISTS",
        )


class InvalidCredentialsError(AppException):
    def __init__(self, detail: str = "Invalid email or password."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="INVALID_CREDENTIALS",
        )


class UnauthorizedAccessError(AppException):
    def __init__(self, detail: str = "Could not validate authentication credentials."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="UNAUTHORIZED",
        )


class ForbiddenOperationError(AppException):
    def __init__(self, detail: str = "You do not have permission to access or modify this resource."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN_OPERATION",
        )


class InvalidStateTransitionError(AppException):
    def __init__(self, current_state: str, attempted_state: str, reason: str = ""):
        message = f"Cannot transition booking from state '{current_state}' to '{attempted_state}'."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
            error_code="INVALID_STATE_TRANSITION",
        )


class InvalidBookingError(AppException):
    def __init__(self, detail: str, error_code: str = "INVALID_BOOKING"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
        )


class PaymentProcessingError(AppException):
    def __init__(self, detail: str, error_code: str = "PAYMENT_PROCESSING_FAILED"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
        )


class WebhookSignatureError(AppException):
    def __init__(self, detail: str = "Invalid webhook signature."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="INVALID_WEBHOOK_SIGNATURE",
        )
