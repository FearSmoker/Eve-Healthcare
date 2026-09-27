import json
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import generate_webhook_signature
from app.models.centre import CentreTest
from tests.test_payments import _create_booking_helper


def test_webhook_payment_succeeded_and_idempotency(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """successful webhook confirms booking and repeated deliveries are deduplicated idempotently"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)
    event_id = f"evt_test_{uuid.uuid4().hex}"

    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.succeeded",
        "booking_id": booking_id,
        "amount_paise": sample_offering.price_paise,
        "provider_reference": "ref_razorpay_mock_123",
    }

    # first delivery
    response1 = client.post("/api/v1/payments/webhook/", json=webhook_payload)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "processed"
    assert data1["event_id"] == event_id

    booking_res = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert booking_res.json()["status"] == "CONFIRMED"

    # duplicate delivery
    response2 = client.post("/api/v1/payments/webhook/", json=webhook_payload)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "already_processed"
    assert data2["event_id"] == event_id

    # third delivery attempt
    response3 = client.post("/api/v1/payments/webhook/", json=webhook_payload)
    assert response3.status_code == 200
    assert response3.json()["status"] == "already_processed"

    booking_res_after = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert booking_res_after.json()["status"] == "CONFIRMED"


def test_webhook_payment_failed(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """failed payment webhook updates booking to failed status"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)
    event_id = f"evt_fail_{uuid.uuid4().hex}"

    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.failed",
        "booking_id": booking_id,
        "amount_paise": sample_offering.price_paise,
        "provider_reference": "ref_fail_mock_456",
    }

    response = client.post("/api/v1/payments/webhook/", json=webhook_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    booking_res = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert booking_res.json()["status"] == "FAILED"


def test_webhook_nonexistent_booking_returns_404(client: TestClient):
    """webhook referencing nonexistent booking id returns 404"""
    random_booking_id = str(uuid.uuid4())
    event_id = f"evt_missing_{uuid.uuid4().hex}"

    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment.succeeded",
        "booking_id": random_booking_id,
        "amount_paise": 50000,
    }

    response = client.post("/api/v1/payments/webhook/", json=webhook_payload)
    assert response.status_code == 404
    assert response.json()["error_code"] == "BOOKING_NOT_FOUND"


def test_webhook_hmac_signature_validation(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """webhook validates hmac signature header and rejects tampered payloads"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)
    event_id = f"evt_sig_{uuid.uuid4().hex}"

    payload = {
        "event_id": event_id,
        "event_type": "payment.succeeded",
        "booking_id": booking_id,
        "amount_paise": sample_offering.price_paise,
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    # invalid signature rejected
    res_bad = client.post(
        "/api/v1/payments/webhook/",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "invalid_signature_hex",
        },
    )
    assert res_bad.status_code == 401
    assert res_bad.json()["error_code"] == "INVALID_WEBHOOK_SIGNATURE"

    # valid signature accepted
    valid_sig = generate_webhook_signature(raw_bytes)
    res_good = client.post(
        "/api/v1/payments/webhook/",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": valid_sig,
        },
    )
    assert res_good.status_code == 200
    assert res_good.json()["status"] == "processed"


def test_direct_root_webhook_route_compatibility(
    client: TestClient, patient_headers: dict[str, str], sample_offering: CentreTest
):
    """direct root endpoint POST /payments/webhook/ processes events identically to versioned route"""
    booking_id = _create_booking_helper(client, patient_headers, sample_offering)
    event_id = f"evt_root_{uuid.uuid4().hex}"

    response = client.post(
        "/payments/webhook/",
        json={
            "event_id": event_id,
            "event_type": "payment.succeeded",
            "booking_id": booking_id,
            "amount_paise": sample_offering.price_paise,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
