from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.models.centre import CentreTest


def _create_booking_helper(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
) -> str:
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    res = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_test_id": str(sample_offering.id),
            "appointment_datetime": future_time,
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_simulate_payment_success(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """simulating successful payment updates booking to confirmed and records payment"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)

    response = client.post(
        "/api/v1/payments/",
        headers=patient_headers,
        json={
            "booking_id": booking_id,
            "payment_method": "UPI",
            "simulate_failure": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["booking_status"] == "CONFIRMED"
    assert data["amount_paise"] == sample_offering.price_paise
    assert data["amount_inr"] == 450.0
    assert data["transaction_id"].startswith("txn_sim_")

    booking_res = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert booking_res.json()["status"] == "CONFIRMED"


def test_simulate_payment_failure(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """simulating failed payment updates booking to failed state"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)

    response = client.post(
        "/api/v1/payments/",
        headers=patient_headers,
        json={
            "booking_id": booking_id,
            "payment_method": "CREDIT_CARD",
            "simulate_failure": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["booking_status"] == "FAILED"

    booking_res = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert booking_res.json()["status"] == "FAILED"


def test_prevent_double_payment_on_confirmed_booking(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """attempting to pay for an already confirmed booking returns 409 conflict"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)

    r1 = client.post(
        "/api/v1/payments/",
        headers=patient_headers,
        json={"booking_id": booking_id, "simulate_failure": False},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/payments/",
        headers=patient_headers,
        json={"booking_id": booking_id, "simulate_failure": False},
    )
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "BOOKING_ALREADY_PAID"


def test_cannot_pay_for_cancelled_booking(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """attempting to pay for a cancelled booking returns 409 invalid state transition"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)

    client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=patient_headers)

    r = client.post(
        "/api/v1/payments/",
        headers=patient_headers,
        json={"booking_id": booking_id},
    )
    assert r.status_code == 409
    assert r.json()["error_code"] == "INVALID_STATE_TRANSITION"


def test_cannot_pay_for_other_user_booking(
    client: TestClient,
    patient_headers: dict[str, str],
    other_patient_headers: dict[str, str],
    sample_offering: CentreTest,
):
    """paying for another user's booking returns 403 forbidden"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)

    r = client.post(
        "/api/v1/payments/",
        headers=other_patient_headers,
        json={"booking_id": booking_id},
    )
    assert r.status_code == 403
    assert r.json()["error_code"] == "FORBIDDEN_OPERATION"


def test_direct_root_payment_endpoint_compatibility(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """direct root endpoint POST /payments/ processes payment identically to versioned route"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)
    response = client.post(
        "/payments/",
        headers=patient_headers,
        json={"booking_id": booking_id, "simulate_failure": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
