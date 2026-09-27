import pytest
from fastapi.testclient import TestClient

from app.models.centre import CentreTest


def test_list_centres_empty(client: TestClient):
    """fetching centres when none exist returns empty list with total 0"""
    response = client.get("/api/v1/centres")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_create_centre_as_admin(client: TestClient, admin_headers: dict[str, str]):
    """admin user can create a diagnostic centre with 201 status"""
    response = client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "EVE Lab Indiranagar",
            "address": "100 Feet Rd",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560038",
            "contact_phone": "+918025251122",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "EVE Lab Indiranagar"
    assert data["city"] == "Bengaluru"


def test_create_centre_forbidden_for_patient(
    client: TestClient, patient_headers: dict[str, str]
):
    """non-admin patient cannot create centres and receives 403 forbidden"""
    response = client.post(
        "/api/v1/centres",
        headers=patient_headers,
        json={
            "name": "Unauthorized Lab",
            "address": "Some St",
            "city": "Bengaluru",
            "pincode": "560001",
        },
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_OPERATION"


def test_filter_centres_by_city(
    client: TestClient, admin_headers: dict[str, str]
):
    """querying centres by city filters results correctly"""
    client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "Bangalore Lab",
            "address": "MG Road",
            "city": "Bengaluru",
            "pincode": "560001",
        },
    )
    client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "Mumbai Lab",
            "address": "Bandra",
            "city": "Mumbai",
            "pincode": "400050",
        },
    )

    res_mumbai = client.get("/api/v1/centres?city=Mumbai")
    assert res_mumbai.status_code == 200
    assert res_mumbai.json()["total"] == 1
    assert res_mumbai.json()["items"][0]["city"] == "Mumbai"


def test_get_centre_detail_with_tests_and_pricing(
    client: TestClient, sample_offering: CentreTest
):
    """centre detail includes all offered tests and per-centre prices in paise and inr"""
    centre_id = str(sample_offering.centre_id)
    response = client.get(f"/api/v1/centres/{centre_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == centre_id
    assert len(data["centre_tests"]) == 1

    offering = data["centre_tests"][0]
    assert offering["price_paise"] == 45000
    assert offering["price_inr"] == 450.0
    assert offering["test"]["code"] == "CBC"


def test_create_and_list_tests(
    client: TestClient, admin_headers: dict[str, str]
):
    """admin can create test definition and public catalog lists it"""
    res_create = client.post(
        "/api/v1/tests",
        headers=admin_headers,
        json={
            "name": "Lipid Profile",
            "code": "LIPID",
            "category": "Pathology",
            "description": "Cholesterol & Triglycerides",
        },
    )
    assert res_create.status_code == 201

    res_list = client.get("/api/v1/tests")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "LIPID"
