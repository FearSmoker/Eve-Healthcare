from typing import Generator
from sqlalchemy.orm import Session
from app.db.base import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields an active database session and ensures it closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
