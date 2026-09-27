import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.worker.tasks import (
    notify_booking_created,
    notify_payment_result,
    retry_webhook_processing,
)


def test_redis_cache_primitives(mock_redis):
    """low-level cache set, get, delete, and pattern scan deletion"""
    key = "eve:test:key1"
    cache_set(key, {"foo": "bar", "num": 123}, ttl=60)
    val = cache_get(key)
    assert val == {"foo": "bar", "num": 123}

    cache_delete(key)
    assert cache_get(key) is None

    cache_set("eve:test:pat:1", "a", ttl=60)
    cache_set("eve:test:pat:2", "b", ttl=60)
    cache_delete_pattern("eve:test:pat:*")
    assert cache_get("eve:test:pat:1") is None
    assert cache_get("eve:test:pat:2") is None


def test_centres_api_caching(client: TestClient, admin_headers: dict[str, str], mock_redis):
    """centres list api responses are cached in redis and invalidated on new centre creation"""
    res = client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "Cache Test Centre 1",
            "address": "123 Main St",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
        },
    )
    assert res.status_code == 201

    res1 = client.get("/api/v1/centres?city=Bengaluru")
    assert res1.status_code == 200
    assert len(res1.json()["items"]) == 1

    cached = cache_get("eve:centres:list:Bengaluru::1:10")
    assert cached is not None
    assert len(cached["items"]) == 1

    res_add = client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "Cache Test Centre 2",
            "address": "456 Side St",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560002",
        },
    )
    assert res_add.status_code == 201

    assert cache_get("eve:centres:list:Bengaluru::1:10") is None

    res2 = client.get("/api/v1/centres?city=Bengaluru")
    assert res2.status_code == 200
    assert len(res2.json()["items"]) == 2


def test_celery_notify_booking_created_task():
    """notify_booking_created background task runs and returns sent status"""
    res = notify_booking_created.apply(
        kwargs={
            "booking_id": "test-b-1",
            "patient_name": "Priya Patel",
            "patient_email": "priya@example.com",
            "test_name": "CBC",
            "centre_name": "Apollo Hub",
            "appointment_dt": "2027-02-01T09:00:00",
            "amount_paise": 45000,
        }
    )
    result = res.result
    assert result["task"] == "notify_booking_created"
    assert result["recipient"] == "priya@example.com"
    assert result["status"] == "sent"


def test_celery_notify_payment_result_task():
    """notify_payment_result task executes for success and failed payments"""
    res_ok = notify_payment_result.apply(
        kwargs={
            "booking_id": "test-b-2",
            "patient_name": "Priya Patel",
            "patient_email": "priya@example.com",
            "test_name": "CBC",
            "centre_name": "Apollo Hub",
            "appointment_dt": "2027-02-01T09:00:00",
            "transaction_id": "TXN_OK_123",
            "payment_method": "UPI",
            "amount_paise": 45000,
            "payment_status": "SUCCESS",
            "booking_status": "CONFIRMED",
        }
    )
    assert res_ok.result["payment_status"] == "SUCCESS"
    assert res_ok.result["status"] == "sent"

    res_fail = notify_payment_result.apply(
        kwargs={
            "booking_id": "test-b-3",
            "patient_name": "Priya Patel",
            "patient_email": "priya@example.com",
            "test_name": "CBC",
            "centre_name": "Apollo Hub",
            "appointment_dt": "2027-02-01T09:00:00",
            "transaction_id": "TXN_FAIL_123",
            "payment_method": "UPI",
            "amount_paise": 45000,
            "payment_status": "FAILED",
            "booking_status": "FAILED",
        }
    )
    assert res_fail.result["payment_status"] == "FAILED"
    assert res_fail.result["status"] == "sent"


def test_celery_retry_webhook_processing_already_processed(db: Session):
    """retry_webhook_processing task skips already processed webhook events idempotently"""
    evt_id = f"evt-processed-{uuid.uuid4().hex[:6]}"
    evt = WebhookEvent(
        event_id=evt_id,
        event_type="payment.succeeded",
        raw_payload={"event_id": evt_id, "status": "SUCCESS"},
        processing_status=WebhookStatus.PROCESSED.value,
    )
    db.add(evt)
    db.commit()

    res = retry_webhook_processing.apply(
        kwargs={"event_id": evt_id, "payload_dict": evt.raw_payload}
    )
    assert res.result["result"] == "already_processed"


def test_admin_webhook_retry_endpoint(
    client: TestClient, admin_headers: dict[str, str], db: Session
):
    """admin endpoint enqueues failed webhook for celery reprocessing with 202 accepted"""
    evt_id = f"evt-failed-{uuid.uuid4().hex[:6]}"
    payload = {
        "event_id": evt_id,
        "event_type": "payment.succeeded",
        "booking_id": str(uuid.uuid4()),
        "amount_paise": 45000,
        "status": "FAILED",
    }
    evt = WebhookEvent(
        event_id=evt_id,
        event_type="payment.succeeded",
        raw_payload=payload,
        processing_status=WebhookStatus.FAILED.value,
    )
    db.add(evt)
    db.commit()

    response = client.post(
        f"/api/v1/admin/webhooks/{evt_id}/retry",
        headers=admin_headers,
    )
    assert response.status_code == 202
    data = response.json()
    assert data["event_id"] == evt_id
    assert "task_id" in data


def test_admin_webhook_retry_already_processed_returns_409(
    client: TestClient, admin_headers: dict[str, str], db: Session
):
    """admin retry on already processed webhook returns 409 conflict"""
    evt_id = f"evt-done-{uuid.uuid4().hex[:6]}"
    evt = WebhookEvent(
        event_id=evt_id,
        event_type="payment.succeeded",
        raw_payload={"event_id": evt_id},
        processing_status=WebhookStatus.PROCESSED.value,
    )
    db.add(evt)
    db.commit()

    response = client.post(
        f"/api/v1/admin/webhooks/{evt_id}/retry",
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "WEBHOOK_ALREADY_PROCESSED"


def test_admin_webhook_retry_nonexistent_returns_404(
    client: TestClient, admin_headers: dict[str, str]
):
    """admin retry on nonexistent event id returns 404"""
    response = client.post(
        "/api/v1/admin/webhooks/non-existent-event/retry",
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "WEBHOOKEVENT_NOT_FOUND"
