from datetime import datetime, timedelta, timezone
from typing import Generator
import pytest
import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models.centre import CentreTest, DiagnosticCentre, DiagnosticTest
from app.models.user import User, UserRole

# Use SQLite in-memory with StaticPool to share connection across threads
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# isolation fixtures
@pytest.fixture(autouse=True)
def mock_redis():
    # in-memory redis mock for tests
    import app.core.cache as cache_module
    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)
    original = cache_module._redis_client
    cache_module._redis_client = fake
    yield fake
    cache_module._redis_client = original


@pytest.fixture(autouse=True)
def celery_eager_mode():
    # execute celery tasks synchronously in tests
    from app.worker.celery_app import celery_app as _celery
    import app.worker.tasks as worker_tasks

    _celery.conf.update(task_always_eager=True, task_eager_propagates=False)
    orig_get_db = worker_tasks._get_db_session
    worker_tasks._get_db_session = lambda: TestingSessionLocal()
    yield
    worker_tasks._get_db_session = orig_get_db
    _celery.conf.update(task_always_eager=False, task_eager_propagates=False)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create fresh database tables for each test function and drop after."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient that uses the isolated test database session."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate-limiter in-memory storage before each test so tests are
    # fully isolated and don't bleed rate-limit state into each other.
    from app.core.limiter import limiter
    limiter._storage.reset()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db: Session) -> User:
    """Create and return an admin user."""
    user = User(
        email="test_admin@evehealthcare.com",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin Test User",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    """Bearer authorization headers for admin user."""
    token = create_access_token(subject=str(admin_user.id), role=admin_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def patient_user(db: Session) -> User:
    """Create and return a standard patient user."""
    user = User(
        email="test_patient@evehealthcare.com",
        password_hash=hash_password("PatientPass123!"),
        full_name="Patient Test User",
        role=UserRole.PATIENT.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def patient_headers(patient_user: User) -> dict[str, str]:
    """Bearer authorization headers for patient user."""
    token = create_access_token(subject=str(patient_user.id), role=patient_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_patient_user(db: Session) -> User:
    """Create a second distinct patient to test authorization boundaries."""
    user = User(
        email="other_patient@evehealthcare.com",
        password_hash=hash_password("OtherPatientPass123!"),
        full_name="Other Patient",
        role=UserRole.PATIENT.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_patient_headers(other_patient_user: User) -> dict[str, str]:
    token = create_access_token(subject=str(other_patient_user.id), role=other_patient_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_offering(db: Session) -> CentreTest:
    """Create a sample centre, test, and link offering (price = 45000 paise / ₹450.00)."""
    centre = DiagnosticCentre(
        name="Apollo Diagnostic Hub",
        address="123 Hospital Road",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        contact_phone="+918012345678",
        is_active=True,
    )
    test = DiagnosticTest(
        name="Complete Blood Count",
        code="CBC",
        category="Pathology",
        description="Routine hematology profile",
        preparation_instructions="No fasting required",
        is_active=True,
    )
    db.add(centre)
    db.add(test)
    db.commit()

    link = CentreTest(
        centre_id=centre.id,
        test_id=test.id,
        price_paise=45000,
        is_available=True,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
