import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.centre import CentreTest


def test_create_booking_success(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """create booking with valid offering and future datetime returns pending booking with frozen price"""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": future_time,
            "notes": "Patient prefers morning slot.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["amount_paise"] == sample_offering.price_paise
    assert data["amount_inr"] == 450.0
    assert data["centre_name"] == "Apollo Diagnostic Hub"
    assert data["test_name"] == "Complete Blood Count"


def test_create_booking_past_datetime_fails(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """booking appointment in the past fails validation with 422"""
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": past_time,
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_create_booking_nonexistent_centre_test(
    client: TestClient, patient_headers: dict[str, str]
):
    """booking an unknown centre test offering returns 404"""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    random_uuid = str(uuid.uuid4())
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": random_uuid,
            "appointment_datetime": future_time,
        },
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "DIAGNOSTIC_TEST_OFFERING_NOT_FOUND"


def test_list_bookings_patient_isolation(
    client: TestClient,
    patient_headers: dict[str, str],
    other_patient_headers: dict[str, str],
    sample_offering: CentreTest,
):
    """patients can only see their own bookings and cannot view bookings of others"""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": future_time,
        },
    )

    res1 = client.get("/api/v1/bookings", headers=patient_headers)
    assert res1.status_code == 200
    assert res1.json()["total"] == 1

    res2 = client.get("/api/v1/bookings", headers=other_patient_headers)
    assert res2.status_code == 200
    assert res2.json()["total"] == 0


def test_get_booking_ownership_forbidden_for_other_user(
    client: TestClient,
    patient_headers: dict[str, str],
    other_patient_headers: dict[str, str],
    sample_offering: CentreTest,
):
    """accessing another patient's booking by id returns 403 forbidden"""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_res = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": future_time,
        },
    )
    booking_id = create_res.json()["id"]

    res_owner = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert res_owner.status_code == 200

    res_other = client.get(f"/api/v1/bookings/{booking_id}", headers=other_patient_headers)
    assert res_other.status_code == 403
    assert res_other.json()["error_code"] == "FORBIDDEN_OPERATION"


def test_cancel_booking_success_and_prevent_double_cancel(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """cancelling a pending booking succeeds and repeated cancellation returns 409 conflict"""
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_res = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": future_time,
        },
    )
    booking_id = create_res.json()["id"]

    cancel_res = client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=patient_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    cancel_res_again = client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=patient_headers,
    )
    assert cancel_res_again.status_code == 409
    assert cancel_res_again.json()["error_code"] == "INVALID_STATE_TRANSITION"
