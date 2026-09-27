import pytest
from fastapi.testclient import TestClient


def test_user_signup_success(client: TestClient):
    """successful user registration returns created patient profile without password hash"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test Candidate",
            "phone": "+919999888877",
            "role": "PATIENT",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new_user@example.com"
    assert data["full_name"] == "Test Candidate"
    assert data["role"] == "PATIENT"
    assert "id" in data
    assert "password_hash" not in data


def test_user_signup_duplicate_email(client: TestClient):
    """registering with an existing email returns 409 conflict"""
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
        "full_name": "First User",
    }
    r1 = client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/auth/signup", json=payload)
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "USER_ALREADY_EXISTS"


def test_user_signup_short_password_fails_validation(client: TestClient):
    """passwords under 8 characters fail schema validation with 422"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "shortpass@example.com",
            "password": "123",
            "full_name": "Short Pass User",
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_user_login_success(client: TestClient):
    """valid credentials return jwt access token and user metadata"""
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "login_user@example.com",
            "password": "CorrectPassword123!",
            "full_name": "Login User",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login_user@example.com",
            "password": "CorrectPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_user@example.com"


def test_user_login_invalid_password(client: TestClient):
    """incorrect password returns 401 invalid credentials"""
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "wrong_pass@example.com",
            "password": "CorrectPassword123!",
            "full_name": "User",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong_pass@example.com",
            "password": "IncorrectPassword!",
        },
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"


def test_user_login_nonexistent_email(client: TestClient):
    """unregistered email returns 401 without user enumeration"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "AnyPassword123!",
        },
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"


def test_get_current_profile_authenticated(client: TestClient, patient_headers: dict[str, str]):
    """authenticated user can fetch their own profile from /auth/me"""
    response = client.get("/api/v1/auth/me", headers=patient_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test_patient@evehealthcare.com"
    assert data["role"] == "PATIENT"


def test_get_current_profile_unauthenticated(client: TestClient):
    """missing authorization header returns 401 unauthorized"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"
