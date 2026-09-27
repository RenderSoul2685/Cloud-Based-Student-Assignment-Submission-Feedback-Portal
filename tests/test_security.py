"""
Automated Test Suite for Security Hardening Pass.
Verifies:
1. Rate limiting on sensitive endpoints (/api/register, /submit, /grade) returning HTTP 429.
2. Pydantic schema max_length constraints and email validation returning HTTP 422.
3. CORS origin enforcement based on configured ALLOWED_ORIGINS.
"""
import sys
import os
import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.limiter import limiter
from backend.app.models.models import UserRole, SubmissionStatus
from backend.app.routes.auth_routes import get_db_service as auth_get_db, get_auth_service as auth_get_auth
from backend.app.routes.course_routes import get_db_service as course_get_db
from backend.app.routes.assignment_routes import get_db_service as assign_get_db
from backend.app.routes.submission_routes import (
    get_db_service as sub_get_db,
    get_storage_service as sub_get_storage,
)
from backend.app.middleware.auth_middleware import get_db_service as mw_get_db


class MockUserRecord:
    def __init__(self, uid: str, email: str, display_name: str):
        self.uid = uid
        self.email = email
        self.display_name = display_name


class MockAuthService:
    def __init__(self):
        self.users = {}

    def create_user(self, email: str, password: str, display_name: str = None):
        uid = f"mock-uid-{len(self.users) + 1}"
        record = MockUserRecord(uid=uid, email=email, display_name=display_name)
        self.users[uid] = record
        return record

    def set_user_role(self, uid: str, role: str) -> None:
        pass


class MockStorageService:
    def __init__(self):
        self.uploaded_files = {}

    def upload_file(self, file_data, storage_path, content_type=None):
        if hasattr(file_data, "read"):
            data = file_data.read()
        else:
            data = file_data
        self.uploaded_files[storage_path] = data
        return storage_path

    def get_download_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        return f"https://storage.googleapis.com/mock/{storage_path}"


class MockDatabaseService:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.users = {
            "student-1": {"uid": "student-1", "email": "student@portal.edu", "name": "Alice Student", "role": "STUDENT"},
            "teacher-1": {"uid": "teacher-1", "email": "teacher@portal.edu", "name": "Prof Smith", "role": "TEACHER"},
        }
        self.courses = {
            "course-1": {
                "course_id": "course-1",
                "course_name": "Cloud Computing",
                "title": "Cloud Computing",
                "description": "Intro to Cloud",
                "teacher_id": "teacher-1",
                "created_by": "teacher-1",
                "enrolled_student_ids": ["student-1"],
                "is_deleted": False,
            }
        }
        self.assignments = {
            ("course-1", "assign-1"): {
                "assignment_id": "assign-1",
                "course_id": "course-1",
                "title": "Assignment 1",
                "description": "Upload report",
                "deadline": "2099-12-31T23:59:59Z",
                "max_marks": 100.0,
                "allowed_file_types": "pdf",
                "max_file_size_mb": 10.0,
                "allow_late_submission": True,
                "resubmission_allowed": True,
                "created_by": "teacher-1",
                "is_deleted": False,
            }
        }
        self.submissions = {}

    def get_user(self, uid: str):
        if uid in self.users:
            return {"uid": uid, **self.users[uid]}
        return None

    def create_user(self, uid: str, data: dict):
        self.users[uid] = data
        return {"uid": uid, **data}

    def get_course(self, course_id: str):
        if course_id in self.courses:
            return {"course_id": course_id, **self.courses[course_id]}
        return None

    def create_course(self, course_id: str, data: dict):
        self.courses[course_id] = data
        return {"course_id": course_id, **data}

    def get_assignment(self, course_id: str, assignment_id: str):
        key = (course_id, assignment_id)
        if key in self.assignments:
            return {"assignment_id": assignment_id, "course_id": course_id, **self.assignments[key]}
        return None

    def find_assignment_by_id(self, assignment_id: str):
        for (c_id, a_id), data in self.assignments.items():
            if a_id == assignment_id:
                return {"assignment_id": a_id, "course_id": c_id, **data}
        return None

    def create_assignment(self, course_id: str, assignment_id: str, data: dict):
        self.assignments[(course_id, assignment_id)] = data
        return {"assignment_id": assignment_id, "course_id": course_id, **data}

    def get_submission(self, submission_id: str):
        if submission_id in self.submissions:
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None

    def get_submission_by_student_and_assignment(self, assignment_id: str, student_id: str):
        for s_id, s_data in self.submissions.items():
            if s_data.get("student_id") == student_id and s_data.get("assignment_id") == assignment_id:
                return {"submission_id": s_id, **s_data}
        return None

    def create_submission(self, submission_id: str, data: dict):
        self.submissions[submission_id] = data.copy()
        return {"submission_id": submission_id, **data}

    def update_submission(self, submission_id: str, data: dict):
        if submission_id in self.submissions:
            self.submissions[submission_id].update(data)
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None


@pytest.fixture
def sec_setup():
    mock_db = MockDatabaseService()
    mock_auth = MockAuthService()
    mock_storage = MockStorageService()

    app.dependency_overrides[auth_get_db] = lambda: mock_db
    app.dependency_overrides[auth_get_auth] = lambda: mock_auth
    app.dependency_overrides[mw_get_db] = lambda: mock_db
    app.dependency_overrides[course_get_db] = lambda: mock_db
    app.dependency_overrides[assign_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_storage] = lambda: mock_storage

    def mock_verify_token(token: str):
        if token == "student-token":
            return {"uid": "student-1", "email": "student@portal.edu"}
        elif token == "teacher-token":
            return {"uid": "teacher-1", "email": "teacher@portal.edu"}
        raise ValueError("Invalid token")

    limiter.reset()

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_verify_token):
        client = TestClient(app)
        yield client, mock_db, mock_auth, mock_storage

    app.dependency_overrides.clear()
    limiter.reset()


def test_rate_limit_register_endpoint(sec_setup):
    """Confirm POST /api/register enforces 5 attempts per minute per IP, returning 429 on 6th."""
    client, mock_db, mock_auth, mock_storage = sec_setup

    for i in range(5):
        resp = client.post("/api/register", json={
            "email": f"user{i}@test.edu",
            "password": "Password123!",
            "name": f"User {i}",
            "role": "STUDENT"
        })
        assert resp.status_code == 201

    # 6th request within the minute window must trigger HTTP 429
    resp_blocked = client.post("/api/register", json={
        "email": "user6@test.edu",
        "password": "Password123!",
        "name": "User Six",
        "role": "STUDENT"
    })
    assert resp_blocked.status_code == 429
    data = resp_blocked.json()
    assert "error" in data or "detail" in data


def test_rate_limit_submit_endpoint(sec_setup):
    """Confirm POST /api/assignments/{id}/submit enforces 10 submissions/min, returning 429 on 11th."""
    client, mock_db, mock_auth, mock_storage = sec_setup
    headers = {"Authorization": "Bearer student-token"}

    for i in range(10):
        pdf_content = b"%PDF-1.4 Mock PDF content " + str(i).encode()
        files = {"file": (f"test_{i}.pdf", io.BytesIO(pdf_content), "application/pdf")}
        resp = client.post("/api/assignments/assign-1/submit", headers=headers, files=files)
        assert resp.status_code == 200 or resp.status_code == 201

    # 11th request must trigger HTTP 429
    pdf_content = b"%PDF-1.4 Mock PDF content extra"
    files = {"file": ("test_11.pdf", io.BytesIO(pdf_content), "application/pdf")}
    resp_blocked = client.post("/api/assignments/assign-1/submit", headers=headers, files=files)
    assert resp_blocked.status_code == 429


def test_rate_limit_grade_endpoint(sec_setup):
    """Confirm PUT /api/submissions/{id}/grade enforces 30 requests/min, returning 429 on 31st."""
    client, mock_db, mock_auth, mock_storage = sec_setup
    headers = {"Authorization": "Bearer teacher-token"}

    # Create submission in db to grade
    mock_db.create_submission("sub-rate-limit-test", {
        "assignment_id": "assign-1",
        "course_id": "course-1",
        "student_id": "student-1",
        "file_name": "sub.pdf",
        "storage_path": "submissions/course-1/assign-1/student-1/sub.pdf",
        "file_url": "gs://test-bucket/sub.pdf",
        "submitted_at": datetime.now(timezone.utc),
        "submission_status": SubmissionStatus.SUBMITTED.value,
        "is_deleted": False,
        "resubmission_count": 0,
    })

    for i in range(30):
        resp = client.put(
            "/api/submissions/sub-rate-limit-test/grade",
            headers=headers,
            json={"marks": 85.0, "feedback": f"Feedback attempt {i}"}
        )
        assert resp.status_code == 200

    # 31st request must trigger HTTP 429
    resp_blocked = client.put(
        "/api/submissions/sub-rate-limit-test/grade",
        headers=headers,
        json={"marks": 90.0, "feedback": "Blocked attempt"}
    )
    assert resp_blocked.status_code == 429


def test_schema_string_max_length_constraints(sec_setup):
    """Confirm free-text fields exceeding max_length are rejected with 422 Unprocessable Entity."""
    client, mock_db, mock_auth, mock_storage = sec_setup
    teacher_headers = {"Authorization": "Bearer teacher-token"}

    # 1. User name exceeding 255 chars
    oversized_name = "A" * 256
    resp = client.post("/api/register", json={
        "email": "testlength@portal.edu",
        "password": "Password123!",
        "name": oversized_name,
        "role": "STUDENT"
    })
    assert resp.status_code == 422

    # 2. Course title exceeding 255 chars
    resp = client.post("/api/courses", headers=teacher_headers, json={
        "title": "T" * 256,
        "description": "Valid description"
    })
    assert resp.status_code == 422

    # 3. Course description exceeding 2000 chars
    resp = client.post("/api/courses", headers=teacher_headers, json={
        "title": "Valid Title",
        "description": "D" * 2001
    })
    assert resp.status_code == 422

    # 4. Assignment title exceeding 255 chars
    resp = client.post("/api/courses/course-1/assignments", headers=teacher_headers, json={
        "title": "A" * 256,
        "description": "Valid description",
        "deadline": "2099-12-31T23:59:59Z",
        "max_marks": 100
    })
    assert resp.status_code == 422

    # 5. Feedback exceeding 10000 chars on grading
    mock_db.create_submission("sub-len-test", {
        "assignment_id": "assign-1",
        "course_id": "course-1",
        "student_id": "student-1",
        "file_name": "sub.pdf",
        "storage_path": "submissions/course-1/assign-1/student-1/sub.pdf",
        "file_url": "gs://test-bucket/sub.pdf",
        "submitted_at": datetime.now(timezone.utc),
        "submission_status": SubmissionStatus.SUBMITTED.value,
        "is_deleted": False,
        "resubmission_count": 0,
    })
    resp = client.put(
        "/api/submissions/sub-len-test/grade",
        headers=teacher_headers,
        json={"marks": 95.0, "feedback": "F" * 10001}
    )
    assert resp.status_code == 422


def test_schema_email_validation(sec_setup):
    """Confirm malformed email addresses are rejected with 422 Unprocessable Entity."""
    client, mock_db, mock_auth, mock_storage = sec_setup

    malformed_emails = ["notanemail", "missing@domain", "@nodomain.com", "spaces in@email.com"]
    for bad_email in malformed_emails:
        resp = client.post("/api/register", json={
            "email": bad_email,
            "password": "Password123!",
            "name": "Bad Email User",
            "role": "STUDENT"
        })
        assert resp.status_code == 422


def test_cors_headers_handling():
    """Confirm CORS headers respond appropriately for allowed vs untrusted origins."""
    client = TestClient(app)

    # Allowed origin: http://localhost:3000
    resp_allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert resp_allowed.status_code == 200
    assert resp_allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # Untrusted origin: http://evil-hacker-site.org
    resp_untrusted = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil-hacker-site.org",
            "Access-Control-Request-Method": "GET",
        }
    )
    # Origin should not be allowed
    assert resp_untrusted.headers.get("access-control-allow-origin") != "http://evil-hacker-site.org"
