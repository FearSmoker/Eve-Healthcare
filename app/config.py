from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "EVE Healthcare API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./eve_healthcare.db"

    # JWT Settings — must be ≥32 chars in production
    SECRET_KEY: str = "super-secret-eve-healthcare-jwt-token-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Webhook HMAC verification — must be ≥32 chars in production
    WEBHOOK_SECRET: str = "eve_webhook_secret_key_change_me_to_something_long"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True

    # redis and cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = True
    CACHE_TTL_CENTRES_LIST: int = 300
    CACHE_TTL_CENTRE_DETAIL: int = 600
    CACHE_TTL_TESTS_LIST: int = 600

    # celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long for secure JWT signing."
            )
        return v

    @field_validator("WEBHOOK_SECRET")
    @classmethod
    def webhook_secret_min_length(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("WEBHOOK_SECRET must be at least 16 characters.")
        return v


settings = Settings()
