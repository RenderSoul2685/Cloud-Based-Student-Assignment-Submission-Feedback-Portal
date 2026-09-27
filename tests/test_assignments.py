"""
Automated Test Suite for Course and Assignment Management.
Verifies role-based permissions, course ownership, deadline validations,
and soft-delete vs hard-delete behaviors.
"""
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.models.models import UserRole
from backend.app.routes.auth_routes import get_db_service as auth_get_db, get_auth_service
from backend.app.routes.course_routes import get_db_service as course_get_db
from backend.app.routes.assignment_routes import get_db_service as assign_get_db
from backend.app.middleware.auth_middleware import get_db_service as mw_get_db_service


class MockFirestoreDatabase:
    """In-memory Mock Firestore Database with Course, Assignment, and Submission support."""
    def __init__(self):
        self.users = {
            "teacher-uid-smith": {
                "name": "Dr. Robert Smith",
                "email": "smith@portal.edu",
                "role": "TEACHER",
                "created_at": datetime.now(timezone.utc),
            },
            "teacher-uid-jones": {
                "name": "Prof. Sarah Jones",
                "email": "jones@portal.edu",
                "role": "TEACHER",
                "created_at": datetime.now(timezone.utc),
            },
            "student-uid-alice": {
                "name": "Alice Johnson",
                "email": "alice@portal.edu",
                "role": "STUDENT",
                "created_at": datetime.now(timezone.utc),
            },
            "admin-uid-root": {
                "name": "System Administrator",
                "email": "admin@portal.edu",
                "role": "ADMIN",
                "created_at": datetime.now(timezone.utc),
            },
        }

        self.courses = {
            "course-cs501": {
                "course_name": "CS501: Cloud Computing Architecture",
                "description": "Distributed systems, serverless, and cloud patterns",
                "teacher_id": "teacher-uid-smith",
                "created_at": datetime.now(timezone.utc),
            },
            "course-cs502": {
                "course_name": "CS502: Advanced Database Systems",
                "description": "NoSQL document stores and distributed databases",
                "teacher_id": "teacher-uid-jones",
                "created_at": datetime.now(timezone.utc),
            },
        }

        # Key: (course_id, assignment_id) -> data
        self.assignments = {
            ("course-cs501", "assign-101"): {
                "title": "Cloud Storage Sync Implementation",
                "description": "Implement blob upload with signed URL generation",
                "deadline": datetime.now(timezone.utc) + timedelta(days=7),
                "max_marks": 100.0,
                "allowed_file_types": "pdf,docx,zip",
                "max_file_size_mb": 20.0,
                "created_by": "teacher-uid-smith",
                "created_at": datetime.now(timezone.utc),
                "is_deleted": False,
                "deleted_at": None,
            },
            ("course-cs501", "assign-102"): {
                "title": "Unsubmitted Draft Assignment",
                "description": "No students have submitted this assignment yet",
                "deadline": datetime.now(timezone.utc) + timedelta(days=10),
                "max_marks": 50.0,
                "allowed_file_types": "pdf",
                "max_file_size_mb": 10.0,
                "created_by": "teacher-uid-smith",
                "created_at": datetime.now(timezone.utc),
                "is_deleted": False,
                "deleted_at": None,
            },
        }

        # Submissions collection
        self.submissions = {
            "sub-alice-assign-101": {
                "assignment_id": "assign-101",
                "course_id": "course-cs501",
                "student_id": "student-uid-alice",
                "file_name": "alice_assignment.pdf",
                "submission_status": "SUBMITTED",
            }
        }

    # User operations
    def get_user(self, uid: str):
        if uid in self.users:
            return {"uid": uid, **self.users[uid]}
        return None

    # Course operations
    def get_course(self, course_id: str):
        if course_id in self.courses:
            return {"course_id": course_id, **self.courses[course_id]}
        return None

    def list_courses(self):
        return [{"course_id": k, **v} for k, v in self.courses.items()]

    def list_courses_by_teacher(self, teacher_id: str):
        return [{"course_id": k, **v} for k, v in self.courses.items() if v.get("teacher_id") == teacher_id]

    def create_course(self, course_id: str, data: dict):
        self.courses[course_id] = data.copy()
        return {"course_id": course_id, **data}

    # Assignment operations
    def get_assignment(self, course_id: str, assignment_id: str):
        key = (course_id, assignment_id)
        if key in self.assignments:
            return {"assignment_id": assignment_id, "course_id": course_id, **self.assignments[key]}
        return None

    def list_assignments(self, course_id: str, include_deleted: bool = False):
        results = []
        for (c_id, a_id), data in self.assignments.items():
            if c_id == course_id:
                if not include_deleted and data.get("is_deleted") is True:
                    continue
                results.append({"assignment_id": a_id, "course_id": c_id, **data})
        return results

    def create_assignment(self, course_id: str, assignment_id: str, data: dict):
        self.assignments[(course_id, assignment_id)] = data.copy()
        return {"assignment_id": assignment_id, "course_id": course_id, **data}

    def update_assignment(self, course_id: str, assignment_id: str, data: dict):
        key = (course_id, assignment_id)
        if key in self.assignments:
            self.assignments[key].update(data)
            return {"assignment_id": assignment_id, "course_id": course_id, **self.assignments[key]}
        return None

    def delete_assignment(self, course_id: str, assignment_id: str):
        key = (course_id, assignment_id)
        if key in self.assignments:
            del self.assignments[key]
            return True
        return False

    def has_submissions_for_assignment(self, course_id: str, assignment_id: str):
        for sub in self.submissions.values():
            if sub.get("assignment_id") == assignment_id:
                return True
        return False


@pytest.fixture
def test_setup():
    mock_db = MockFirestoreDatabase()

    app.dependency_overrides[auth_get_db] = lambda: mock_db
    app.dependency_overrides[course_get_db] = lambda: mock_db
    app.dependency_overrides[assign_get_db] = lambda: mock_db
    app.dependency_overrides[mw_get_db_service] = lambda: mock_db

    def mock_verify_token(token: str):
        token_map = {
            "token-teacher-smith": {"uid": "teacher-uid-smith", "email": "smith@portal.edu"},
            "token-teacher-jones": {"uid": "teacher-uid-jones", "email": "jones@portal.edu"},
            "token-student-alice": {"uid": "student-uid-alice", "email": "alice@portal.edu"},
            "token-admin-root": {"uid": "admin-uid-root", "email": "admin@portal.edu"},
        }
        if token in token_map:
            return token_map[token]
        raise ValueError("Invalid ID token")

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_verify_token):
        client = TestClient(app)
        yield client, mock_db

    app.dependency_overrides.clear()


# ==============================================================================
# 1. Course Management Tests
# ==============================================================================

def test_student_cannot_create_course(test_setup):
    client, _ = test_setup
    headers = {"Authorization": "Bearer token-student-alice"}

    payload = {"course_name": "CS503: Student Course", "description": "Unauthorized"}
    response = client.post("/api/courses", headers=headers, json=payload)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_teacher_creates_course_success(test_setup):
    client, mock_db = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}

    payload = {"course_name": "CS601: Distributed Cloud", "description": "Advanced Cloud"}
    response = client.post("/api/courses", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["course_name"] == "CS601: Distributed Cloud"
    assert data["teacher_id"] == "teacher-uid-smith"
    assert data["course_id"].startswith("course-")


def test_list_courses_and_list_mine(test_setup):
    client, _ = test_setup

    # Student listing all courses
    headers_student = {"Authorization": "Bearer token-student-alice"}
    res_all = client.get("/api/courses", headers=headers_student)
    assert res_all.status_code == 200
    assert len(res_all.json()) == 2

    # Teacher listing own courses (/api/courses/mine)
    headers_teacher = {"Authorization": "Bearer token-teacher-smith"}
    res_mine = client.get("/api/courses/mine", headers=headers_teacher)
    assert res_mine.status_code == 200
    mine = res_mine.json()
    assert len(mine) == 1
    assert mine[0]["course_id"] == "course-cs501"


# ==============================================================================
# 2. Assignment Authorization & Ownership Tests
# ==============================================================================

def test_student_cannot_create_update_delete_assignment(test_setup):
    client, _ = test_setup
    headers = {"Authorization": "Bearer token-student-alice"}
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    create_payload = {
        "title": "Hacker Assignment",
        "description": "Student creating assignment",
        "deadline": future_time,
        "max_marks": 100.0,
        "allowed_file_types": "pdf",
        "max_file_size_mb": 10.0,
    }

    # POST
    res_create = client.post("/api/courses/course-cs501/assignments", headers=headers, json=create_payload)
    assert res_create.status_code == 403

    # PUT
    res_put = client.put(
        "/api/courses/course-cs501/assignments/assign-101",
        headers=headers,
        json={"title": "Hacked Title"},
    )
    assert res_put.status_code == 403

    # DELETE
    res_del = client.delete("/api/courses/course-cs501/assignments/assign-101", headers=headers)
    assert res_del.status_code == 403


def test_teacher_cannot_modify_other_teachers_assignment(test_setup):
    client, _ = test_setup
    # Teacher Jones attempting to create / modify in Teacher Smith's course (course-cs501)
    headers = {"Authorization": "Bearer token-teacher-jones"}
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    create_payload = {
        "title": "Unauthorized Assignment",
        "description": "Wrong instructor",
        "deadline": future_time,
        "max_marks": 100.0,
        "allowed_file_types": "pdf",
        "max_file_size_mb": 10.0,
    }

    res_post = client.post("/api/courses/course-cs501/assignments", headers=headers, json=create_payload)
    assert res_post.status_code == 403
    assert "not the assigned instructor" in res_post.json()["detail"]

    res_put = client.put(
        "/api/courses/course-cs501/assignments/assign-101",
        headers=headers,
        json={"title": "Unauthorized Update"},
    )
    assert res_put.status_code == 403

    res_del = client.delete("/api/courses/course-cs501/assignments/assign-101", headers=headers)
    assert res_del.status_code == 403


# ==============================================================================
# 3. Assignment Validation Tests (Deadlines & Max Marks)
# ==============================================================================

def test_create_assignment_past_deadline_rejected(test_setup):
    client, _ = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}

    # Past deadline (yesterday)
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    payload = {
        "title": "Late Coursework",
        "description": "Testing past deadline rejection",
        "deadline": past_time,
        "max_marks": 100.0,
        "allowed_file_types": "pdf",
        "max_file_size_mb": 10.0,
    }

    response = client.post("/api/courses/course-cs501/assignments", headers=headers, json=payload)
    assert response.status_code == 400
    assert "must be a future date" in response.json()["detail"]


def test_create_assignment_invalid_marks_rejected(test_setup):
    client, _ = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    payload = {
        "title": "Zero Mark Assignment",
        "description": "Testing max_marks <= 0",
        "deadline": future_time,
        "max_marks": 0.0,
        "allowed_file_types": "pdf",
        "max_file_size_mb": 10.0,
    }

    response = client.post("/api/courses/course-cs501/assignments", headers=headers, json=payload)
    assert response.status_code in (400, 422)


def test_create_assignment_success(test_setup):
    client, mock_db = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}
    future_time = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    payload = {
        "title": "Serverless Architecture Project",
        "description": "Design a complete serverless event-driven architecture.",
        "deadline": future_time,
        "max_marks": 100.0,
        "allowed_file_types": "pdf,docx,zip",
        "max_file_size_mb": 25.0,
    }

    response = client.post("/api/courses/course-cs501/assignments", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Serverless Architecture Project"
    assert data["course_id"] == "course-cs501"
    assert data["created_by"] == "teacher-uid-smith"
    assert data["max_marks"] == 100.0
    assert data["is_deleted"] is False


# ==============================================================================
# 4. Soft-Delete vs Hard-Delete Tests
# ==============================================================================

def test_delete_assignment_with_submissions_soft_deletes(test_setup):
    client, mock_db = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}

    # assign-101 has submissions from Alice in mock_db
    assert mock_db.has_submissions_for_assignment("course-cs501", "assign-101") is True

    response = client.delete("/api/courses/course-cs501/assignments/assign-101", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["soft_deleted"] is True
    assert "soft-deleted" in data["message"]

    # Verify it is marked is_deleted=True in database
    assign_doc = mock_db.get_assignment("course-cs501", "assign-101")
    assert assign_doc["is_deleted"] is True
    assert assign_doc["deleted_at"] is not None

    # Verify GET /api/courses/{course_id}/assignments excludes it from active list
    list_res = client.get("/api/courses/course-cs501/assignments", headers=headers)
    active_ids = [a["assignment_id"] for a in list_res.json()]
    assert "assign-101" not in active_ids


def test_delete_assignment_without_submissions_hard_deletes(test_setup):
    client, mock_db = test_setup
    headers = {"Authorization": "Bearer token-teacher-smith"}

    # assign-102 has NO submissions in mock_db
    assert mock_db.has_submissions_for_assignment("course-cs501", "assign-102") is False

    response = client.delete("/api/courses/course-cs501/assignments/assign-102", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["soft_deleted"] is False
    assert "deleted successfully" in data["message"]

    # Verify it is removed completely
    assert mock_db.get_assignment("course-cs501", "assign-102") is None


# ==============================================================================
# 5. Read Endpoints for Students & Teachers
# ==============================================================================

def test_student_and_teacher_can_read_assignments(test_setup):
    client, _ = test_setup

    # Student reading course assignments
    headers_student = {"Authorization": "Bearer token-student-alice"}
    res_student = client.get("/api/courses/course-cs501/assignments", headers=headers_student)
    assert res_student.status_code == 200
    assert len(res_student.json()) >= 1

    # Single assignment detail
    res_detail = client.get("/api/courses/course-cs501/assignments/assign-102", headers=headers_student)
    assert res_detail.status_code == 200
    assert res_detail.json()["assignment_id"] == "assign-102"
