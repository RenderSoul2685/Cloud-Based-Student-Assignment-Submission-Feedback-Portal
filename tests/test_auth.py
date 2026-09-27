"""
Automated Test Suite for Authentication and Role-Based Authorization (RBAC).
Verifies /api/register, /api/me, /api/teacher-only, and /api/student-only.
"""
import sys
import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.models.models import UserRole, USERS_COLLECTION
from backend.app.routes.auth_routes import get_db_service, get_auth_service
from backend.app.middleware.auth_middleware import get_db_service as mw_get_db_service
from cloud.database_service import DatabaseService
from cloud.auth_service import AuthService


class MockUserRecord:
    """Mock Firebase Auth User Record."""
    def __init__(self, uid: str, email: str, display_name: str):
        self.uid = uid
        self.email = email
        self.display_name = display_name


class InMemoryAuthService:
    """In-memory Mock AuthService for token verification & user creation."""
    def __init__(self):
        self.users = {}
        self.custom_claims = {}

    def verify_firebase_token(self, token: str) -> dict:
        if token == "student-token":
            return {"uid": "student-uid-alice", "email": "alice@portal.edu"}
        elif token == "teacher-token":
            return {"uid": "teacher-uid-smith", "email": "smith@portal.edu"}
        elif token == "admin-token":
            return {"uid": "admin-uid-root", "email": "admin@portal.edu"}
        elif token == "orphan-token":
            return {"uid": "non-existent-uid", "email": "orphan@portal.edu"}
        raise ValueError("Invalid Firebase ID token signature")

    def verify_token(self, token: str) -> dict:
        return self.verify_firebase_token(token)

    def create_user(self, email: str, password: str, display_name: str = None) -> MockUserRecord:
        for u in self.users.values():
            if u.email == email:
                raise Exception("EMAIL_EXISTS")
        uid = f"mock-uid-{len(self.users) + 1}"
        record = MockUserRecord(uid=uid, email=email, display_name=display_name)
        self.users[uid] = record
        return record

    def set_user_role(self, uid: str, role: str) -> None:
        self.custom_claims[uid] = {"role": role}


class InMemoryDatabaseService:
    """In-memory Mock DatabaseService for Firestore collections."""
    def __init__(self):
        self.users_db = {
            "student-uid-alice": {
                "name": "Alice Johnson",
                "email": "alice@portal.edu",
                "role": "STUDENT",
                "created_at": datetime.now(timezone.utc),
            },
            "teacher-uid-smith": {
                "name": "Dr. Robert Smith",
                "email": "smith@portal.edu",
                "role": "TEACHER",
                "created_at": datetime.now(timezone.utc),
            },
            "admin-uid-root": {
                "name": "System Administrator",
                "email": "admin@portal.edu",
                "role": "ADMIN",
                "created_at": datetime.now(timezone.utc),
            },
        }

    def get_user(self, uid: str):
        if uid in self.users_db:
            return {"uid": uid, **self.users_db[uid]}
        return None

    def create_user(self, uid: str, data: dict):
        self.users_db[uid] = data.copy()
        return {"uid": uid, **data}


@pytest.fixture
def client_and_services():
    """Sets up TestClient with injected in-memory services."""
    mock_db = InMemoryDatabaseService()
    mock_auth = InMemoryAuthService()

    app.dependency_overrides[get_db_service] = lambda: mock_db
    app.dependency_overrides[mw_get_db_service] = lambda: mock_db
    app.dependency_overrides[get_auth_service] = lambda: mock_auth

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_auth.verify_firebase_token):
        client = TestClient(app)
        yield client, mock_db, mock_auth

    app.dependency_overrides.clear()


# ==============================================================================
# 1. Unauthenticated / Missing / Invalid Token Tests (Expect 401)
# ==============================================================================

def test_protected_routes_without_token(client_and_services):
    client, _, _ = client_and_services
    
    for endpoint in ["/api/me", "/api/teacher-only", "/api/student-only"]:
        response = client.get(endpoint)
        assert response.status_code == 401
        assert "Authentication credentials were not provided" in response.json()["detail"]


def test_protected_routes_with_invalid_token(client_and_services):
    client, _, _ = client_and_services
    headers = {"Authorization": "Bearer invalid-garbage-token"}

    for endpoint in ["/api/me", "/api/teacher-only", "/api/student-only"]:
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]


def test_token_with_nonexistent_firestore_user(client_and_services):
    client, _, _ = client_and_services
    headers = {"Authorization": "Bearer orphan-token"}

    response = client.get("/api/me", headers=headers)
    assert response.status_code == 404
    assert "not found in database" in response.json()["detail"]


# ==============================================================================
# 2. Role-Based Access Control Tests (RBAC - Expect 200 or 403)
# ==============================================================================

def test_student_token_cannot_access_teacher_only(client_and_services):
    client, _, _ = client_and_services
    headers = {"Authorization": "Bearer student-token"}

    # Student accessing teacher-only -> 403 Forbidden
    response = client.get("/api/teacher-only", headers=headers)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]

    # Student accessing student-only -> 200 OK
    response_ok = client.get("/api/student-only", headers=headers)
    assert response_ok.status_code == 200
    assert response_ok.json()["message"] == "Access granted: You are authorized to access the Student Portal."

    # Student accessing /api/me -> 200 OK
    me_resp = client.get("/api/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "STUDENT"
    assert me_resp.json()["email"] == "alice@portal.edu"


def test_teacher_token_cannot_access_student_only(client_and_services):
    client, _, _ = client_and_services
    headers = {"Authorization": "Bearer teacher-token"}

    # Teacher accessing student-only -> 403 Forbidden
    response = client.get("/api/student-only", headers=headers)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]

    # Teacher accessing teacher-only -> 200 OK
    response_ok = client.get("/api/teacher-only", headers=headers)
    assert response_ok.status_code == 200
    assert response_ok.json()["message"] == "Access granted: You are authorized to access the Teacher Portal."

    # Teacher accessing /api/me -> 200 OK
    me_resp = client.get("/api/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "TEACHER"
    assert me_resp.json()["name"] == "Dr. Robert Smith"


def test_admin_token_access_to_teacher_only(client_and_services):
    client, _, _ = client_and_services
    headers = {"Authorization": "Bearer admin-token"}

    # Admin accessing teacher-only -> 200 OK (allowed roles include ADMIN)
    response = client.get("/api/teacher-only", headers=headers)
    assert response.status_code == 200


# ==============================================================================
# 3. Registration Tests (/api/register)
# ==============================================================================

def test_register_rejects_admin_role(client_and_services):
    client, _, _ = client_and_services

    payload = {
        "name": "Malicious Admin",
        "email": "hacker@portal.edu",
        "password": "Password123!",
        "role": "ADMIN",
    }
    response = client.post("/api/register", json=payload)
    assert response.status_code == 400
    assert "Registration as ADMIN is not permitted" in response.json()["detail"]


def test_register_student_success(client_and_services):
    client, mock_db, _ = client_and_services

    payload = {
        "name": "Charlie Brown",
        "email": "charlie@portal.edu",
        "password": "Password123!",
        "role": "STUDENT",
    }
    response = client.post("/api/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "charlie@portal.edu"
    assert data["name"] == "Charlie Brown"
    assert data["role"] == "STUDENT"
    assert "uid" in data

    # Verify Firestore document was created
    created_user = mock_db.get_user(data["uid"])
    assert created_user is not None
    assert created_user["name"] == "Charlie Brown"


def test_register_teacher_success(client_and_services):
    client, mock_db, _ = client_and_services

    payload = {
        "name": "Prof. David Clark",
        "email": "david@portal.edu",
        "password": "TeacherPass123!",
        "role": "TEACHER",
    }
    response = client.post("/api/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "david@portal.edu"
    assert data["role"] == "TEACHER"


def test_register_duplicate_email(client_and_services):
    client, _, _ = client_and_services

    payload = {
        "name": "First User",
        "email": "duplicate@portal.edu",
        "password": "SecretPassword123!",
        "role": "STUDENT",
    }
    res1 = client.post("/api/register", json=payload)
    assert res1.status_code == 201

    # Attempt to register with same email
    res2 = client.post("/api/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]
