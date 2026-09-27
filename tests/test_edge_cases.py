import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.models.centre import CentreTest


def test_malformed_uuid_in_path_returns_422(client: TestClient):
    """malformed uuid in path parameter fails validation with 422"""
    response = client.get("/api/v1/centres/not-a-valid-uuid")
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_negative_price_in_test_link_returns_422(
    client: TestClient, admin_headers: dict[str, str], sample_offering: CentreTest
):
    """linking test with negative price fails pydantic validation with 422"""
    centre_id = str(sample_offering.centre_id)
    test_id = str(sample_offering.test_id)
    response = client.post(
        f"/api/v1/centres/{centre_id}/tests",
        headers=admin_headers,
        json={
            "test_id": test_id,
            "price_paise": -500,
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_link_test_to_nonexistent_centre_returns_404(
    client: TestClient, admin_headers: dict[str, str], sample_offering: CentreTest
):
    """linking test to nonexistent centre returns 404"""
    random_centre_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/centres/{random_centre_id}/tests",
        headers=admin_headers,
        json={
            "test_id": str(sample_offering.test_id),
            "price_paise": 50000,
        },
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "DIAGNOSTIC_CENTRE_NOT_FOUND"


def test_health_check_endpoint(client: TestClient):
    """health check endpoint returns 200 ok and connected database status"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "version" in data


def test_request_id_and_timing_headers_present(client: TestClient):
    """x-request-id and timing headers are attached to every response"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers


def test_security_headers_present(client: TestClient):
    """standard security headers nosniff, deny, and xss protection are returned"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


def test_signup_cannot_self_promote_to_admin(client: TestClient):
    """public signup ignores role field and always creates patient account"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "hacker@evil.com",
            "password": "HackerPass123!",
            "full_name": "Evil Hacker",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "PATIENT"


def test_password_max_length_rejected(client: TestClient):
    """passwords over 72 characters are rejected to prevent bcrypt truncation vulnerabilities"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "longpass@example.com",
            "password": "A" * 73,
            "full_name": "Long Password User",
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_webhook_invalid_event_type_rejected(client: TestClient):
    """webhook event types outside payment succeeded and failed return 422"""
    response = client.post(
        "/api/v1/payments/webhook/",
        json={
            "event_id": "evt_invalid_type_test",
            "event_type": "refund.initiated",
            "booking_id": str(uuid.uuid4()),
            "amount_paise": 50000,
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_unauthenticated_booking_access_denied(client: TestClient):
    """unauthenticated access to bookings returns 401 unauthorized"""
    response = client.get("/api/v1/bookings")
    assert response.status_code == 401


def test_patient_cannot_access_other_patient_booking(
    client: TestClient,
    patient_headers: dict[str, str],
    other_patient_headers: dict[str, str],
    sample_offering: CentreTest,
):
    """cross patient access to bookings is rejected with 403 forbidden"""
    appt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    create_res = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={"centre_test_id": str(sample_offering.id), "appointment_datetime": appt},
    )
    assert create_res.status_code == 201
    booking_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/bookings/{booking_id}", headers=other_patient_headers)
    assert get_res.status_code == 403
