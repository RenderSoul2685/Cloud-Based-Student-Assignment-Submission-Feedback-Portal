"""
Automated Cross-Feature & Seam Integration Test Suite.
Tests edge cases, boundary conditions, concurrent-ordering workflows,
delete cascades, mid-session role changes, cross-teacher security matrices,
storage integrity, and input fuzzing.
"""
import sys
import os
import io
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.models.models import UserRole, SubmissionStatus
from backend.app.routes.auth_routes import get_db_service as auth_get_db
from backend.app.routes.course_routes import get_db_service as course_get_db
from backend.app.routes.assignment_routes import get_db_service as assign_get_db
from backend.app.routes.submission_routes import (
    get_db_service as sub_get_db,
    get_storage_service as sub_get_storage,
)
from backend.app.middleware.auth_middleware import get_db_service as mw_get_db_service
from backend.app.utils.deadline_utils import is_late


class MockStorageService:
    """Mock Storage Service simulating Firebase Cloud Storage blob uploads and signed URLs."""
    def __init__(self):
        self.uploaded_files = {}  # storage_path -> bytes
        self.delete_calls = []

    def upload_file(self, file_data, storage_path, content_type=None):
        if hasattr(file_data, "read"):
            data = file_data.read()
        else:
            data = file_data
        self.uploaded_files[storage_path] = data
        return storage_path

    def get_download_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        if storage_path in self.uploaded_files:
            return f"https://storage.googleapis.com/mock-bucket/{storage_path}?expires=3600"
        return f"https://storage.googleapis.com/mock-bucket/{storage_path}?expires=3600"

    def delete_file(self, storage_path: str) -> bool:
        self.delete_calls.append(storage_path)
        if storage_path in self.uploaded_files:
            del self.uploaded_files[storage_path]
            return True
        return False


class MockFirestoreDatabase:
    """In-memory Mock Firestore Database with Users, Courses, Assignments, and Submissions."""
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.users = {
            "teacher-uid-a": {
                "name": "Prof. Alice Teacher",
                "email": "teacher_a@portal.edu",
                "role": "TEACHER",
                "created_at": now,
            },
            "teacher-uid-b": {
                "name": "Prof. Bob Teacher",
                "email": "teacher_b@portal.edu",
                "role": "TEACHER",
                "created_at": now,
            },
            "student-uid-charlie": {
                "name": "Charlie Student",
                "email": "student_c@portal.edu",
                "role": "STUDENT",
                "created_at": now,
            },
            "student-uid-dave": {
                "name": "Dave Student",
                "email": "student_d@portal.edu",
                "role": "STUDENT",
                "created_at": now,
            },
            "admin-uid-root": {
                "name": "Administrator",
                "email": "admin@portal.edu",
                "role": "ADMIN",
                "created_at": now,
            },
        }

        self.courses = {}
        self.assignments = {}  # (course_id, assignment_id) -> dict
        self.submissions = {}  # submission_id -> dict

    # User operations
    def get_user(self, uid: str):
        if uid in self.users:
            return {"uid": uid, **self.users[uid]}
        return None

    def list_users(self, role=None):
        results = []
        for uid, data in self.users.items():
            if not role or data.get("role") == role:
                results.append({"uid": uid, **data})
        return results

    def list_students(self):
        return self.list_users(role="STUDENT")

    # Course operations
    def create_course(self, course_id: str, data: dict):
        self.courses[course_id] = dict(data)
        return {"course_id": course_id, **data}

    def get_course(self, course_id: str):
        if course_id in self.courses:
            return {"course_id": course_id, **self.courses[course_id]}
        return None

    def list_courses(self):
        return [{"course_id": cid, **c} for cid, c in self.courses.items()]

    def list_courses_by_teacher(self, teacher_id: str):
        return [{"course_id": cid, **c} for cid, c in self.courses.items() if c.get("teacher_id") == teacher_id]

    def update_course(self, course_id: str, data: dict):
        if course_id in self.courses:
            self.courses[course_id].update(data)
            return {"course_id": course_id, **self.courses[course_id]}
        return None

    def delete_course(self, course_id: str):
        if course_id in self.courses:
            del self.courses[course_id]
            return True
        return False

    # Assignment operations
    def create_assignment(self, course_id: str, assignment_id: str, data: dict):
        self.assignments[(course_id, assignment_id)] = dict(data)
        return {"assignment_id": assignment_id, "course_id": course_id, **data}

    def get_assignment(self, course_id: str, assignment_id: str):
        key = (course_id, assignment_id)
        if key in self.assignments:
            return {"assignment_id": assignment_id, "course_id": course_id, **self.assignments[key]}
        return None

    def find_assignment_by_id(self, assignment_id: str):
        for (cid, aid), data in self.assignments.items():
            if aid == assignment_id:
                return {"assignment_id": aid, "course_id": cid, **data}
        return None

    def list_assignments(self, course_id: str, include_deleted: bool = False):
        results = []
        for (cid, aid), data in self.assignments.items():
            if cid == course_id:
                if not include_deleted and data.get("is_deleted") is True:
                    continue
                results.append({"assignment_id": aid, "course_id": cid, **data})
        return results

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

    # Submission operations
    def create_submission(self, submission_id: str, data: dict):
        self.submissions[submission_id] = dict(data)
        return {"submission_id": submission_id, **data}

    def get_submission(self, submission_id: str):
        if submission_id in self.submissions:
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None

    def get_submission_by_student_and_assignment(self, assignment_id: str, student_id: str):
        for sid, data in self.submissions.items():
            if data.get("assignment_id") == assignment_id and data.get("student_id") == student_id:
                return {"submission_id": sid, **data}
        return None

    def list_submissions_by_student(self, student_id: str):
        return [
            {"submission_id": sid, **data}
            for sid, data in self.submissions.items()
            if data.get("student_id") == student_id
        ]

    def list_submissions_by_assignment(self, assignment_id: str):
        return [
            {"submission_id": sid, **data}
            for sid, data in self.submissions.items()
            if data.get("assignment_id") == assignment_id
        ]

    def update_submission(self, submission_id: str, data: dict):
        if submission_id in self.submissions:
            self.submissions[submission_id].update(data)
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None

    def has_submissions_for_assignment(self, course_id: str, assignment_id: str):
        for sid, data in self.submissions.items():
            if data.get("assignment_id") == assignment_id:
                return True
        return False


def mock_verify_token(token: str):
    """Simulates token decoding mapping mock token strings to test user UIDs."""
    token_map = {
        "valid-token-teacher-a": {"uid": "teacher-uid-a", "email": "teacher_a@portal.edu"},
        "valid-token-teacher-b": {"uid": "teacher-uid-b", "email": "teacher_b@portal.edu"},
        "valid-token-student-c": {"uid": "student-uid-charlie", "email": "student_c@portal.edu"},
        "valid-token-student-d": {"uid": "student-uid-dave", "email": "student_d@portal.edu"},
        "valid-token-admin": {"uid": "admin-uid-root", "email": "admin@portal.edu"},
    }
    if token in token_map:
        return token_map[token]
    raise ValueError(f"Invalid token: {token}")


@pytest.fixture
def mock_db():
    return MockFirestoreDatabase()


@pytest.fixture
def mock_storage():
    return MockStorageService()


@pytest.fixture
def client(mock_db, mock_storage):
    app.dependency_overrides[auth_get_db] = lambda: mock_db
    app.dependency_overrides[course_get_db] = lambda: mock_db
    app.dependency_overrides[assign_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_db] = lambda: mock_db
    app.dependency_overrides[mw_get_db_service] = lambda: mock_db
    app.dependency_overrides[sub_get_storage] = lambda: mock_storage

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_verify_token):
        with patch("cloud.auth_service.verify_firebase_token", side_effect=mock_verify_token):
            test_client = TestClient(app)
            yield test_client

    app.dependency_overrides.clear()


# ==============================================================================
# 1. DELETE CASCADES: Soft-Delete Cascade & Student Transcript Preservation
# ==============================================================================
def test_delete_course_cascade_preserves_submissions(client, mock_db):
    """
    Scenario 1: Delete a course that has assignments with submissions & grades.
    Confirm soft-delete cascades to assignments, active listings omit the course,
    and a student's /api/submissions/me still shows historical data without losing transcript history.
    """
    # 1. Setup course, assignment, and student submission with grade
    course_id = "course-math101"
    assign_id = "assign-algebra"
    now = datetime.now(timezone.utc)

    mock_db.create_course(course_id, {
        "course_name": "MATH101: Linear Algebra",
        "description": "Matrices and vector spaces",
        "teacher_id": "teacher-uid-a",
        "created_at": now,
    })

    mock_db.create_assignment(course_id, assign_id, {
        "title": "Matrix Inversion Task",
        "description": "Calculate determinant and inverse.",
        "deadline": now + timedelta(days=7),
        "max_marks": 100.0,
        "allowed_file_types": "pdf,docx",
        "max_file_size_mb": 10.0,
        "allow_late_submission": True,
        "resubmission_allowed": True,
        "created_by": "teacher-uid-a",
        "created_at": now,
        "is_deleted": False,
        "deleted_at": None,
    })

    mock_db.create_submission("sub-math-001", {
        "assignment_id": assign_id,
        "course_id": course_id,
        "student_id": "student-uid-charlie",
        "file_name": "charlie_solution.pdf",
        "file_url": "assignments/course-math101/assign-algebra/student-uid-charlie/charlie_solution.pdf",
        "storage_path": "assignments/course-math101/assign-algebra/student-uid-charlie/charlie_solution.pdf",
        "submitted_at": now,
        "submission_status": "GRADED",
        "resubmission_count": 0,
        "marks": 98.0,
        "feedback": "Flawless matrix decomposition!",
        "graded_at": now,
        "graded_by": "teacher-uid-a",
    })

    # 2. Teacher A deletes the course
    res = client.delete(
        f"/api/courses/{course_id}",
        headers={"Authorization": "Bearer valid-token-teacher-a"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["soft_deleted"] is True
    assert data["assignments_affected"] == 1

    # Verify course and assignment in DB are marked is_deleted=True
    assert mock_db.courses[course_id]["is_deleted"] is True
    assert mock_db.assignments[(course_id, assign_id)]["is_deleted"] is True

    # 3. Active course listings omit the soft-deleted course
    list_res = client.get(
        "/api/courses",
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert list_res.status_code == 200
    active_courses = list_res.json()
    assert all(c["course_id"] != course_id for c in active_courses)

    # 4. Student's /api/submissions/me still includes complete historical transcript
    sub_res = client.get(
        "/api/submissions/me",
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert sub_res.status_code == 200
    subs = sub_res.json()
    assert len(subs) == 1
    s = subs[0]
    assert s["submission_id"] == "sub-math-001"
    assert s["course_name"] == "MATH101: Linear Algebra"
    assert s["assignment_title"] == "Matrix Inversion Task"
    assert s["marks"] == 98.0
    assert s["feedback"] == "Flawless matrix decomposition!"
    assert s["submission_status"] == "GRADED"

    # 5. Course with NO submissions hard-deletes cleanly
    empty_course_id = "course-empty101"
    mock_db.create_course(empty_course_id, {
        "course_name": "EMPTY101: No Students",
        "description": "Empty course",
        "teacher_id": "teacher-uid-a",
        "created_at": now,
    })
    del_res = client.delete(
        f"/api/courses/{empty_course_id}",
        headers={"Authorization": "Bearer valid-token-teacher-a"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["soft_deleted"] is False
    assert empty_course_id not in mock_db.courses


# ==============================================================================
# 2. CONCURRENT-ISH RESUBMISSION + GRADING ORDERING
# ==============================================================================
def test_concurrent_grade_then_resubmit_and_resubmit_then_grade(client, mock_db):
    """
    Scenario 2:
    Case A: Teacher grades (v0), then student resubmits (v1) -> grade is reset, status resets to SUBMITTED.
    Case B: Student resubmits (v1), then teacher grades -> grade attaches to the latest file version.
    """
    course_id = "course-eng101"
    assign_id = "assign-essay"
    now = datetime.now(timezone.utc)

    mock_db.create_course(course_id, {
        "course_name": "ENG101: Technical Writing",
        "teacher_id": "teacher-uid-a",
        "created_at": now,
    })

    mock_db.create_assignment(course_id, assign_id, {
        "title": "Research Paper",
        "description": "Write technical report",
        "deadline": now + timedelta(days=5),
        "max_marks": 100.0,
        "allowed_file_types": "pdf",
        "max_file_size_mb": 10.0,
        "allow_late_submission": True,
        "resubmission_allowed": True,
        "created_by": "teacher-uid-a",
        "created_at": now,
        "is_deleted": False,
    })

    # 1. Student submits initial draft v0
    file_v0 = io.BytesIO(b"%PDF-1.4 Initial draft content")
    submit_res = client.post(
        f"/api/assignments/{assign_id}/submit",
        files={"file": ("draft_v1.pdf", file_v0, "application/pdf")},
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert submit_res.status_code == 201
    sub_id = submit_res.json()["submission_id"]
    assert submit_res.json()["resubmission_count"] == 0

    # 2. Case A: Teacher grades v0
    grade_res = client.put(
        f"/api/submissions/{sub_id}/grade",
        json={"marks": 75.0, "feedback": "Needs stronger citations."},
        headers={"Authorization": "Bearer valid-token-teacher-a"},
    )
    assert grade_res.status_code == 200
    assert grade_res.json()["submission_status"] == "GRADED"
    assert grade_res.json()["marks"] == 75.0

    # Student resubmits v1 -> grade MUST be cleared and status reset away from GRADED
    file_v1 = io.BytesIO(b"%PDF-1.4 Revised draft with citations")
    resubmit_res = client.post(
        f"/api/assignments/{assign_id}/submit",
        files={"file": ("draft_v2.pdf", file_v1, "application/pdf")},
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert resubmit_res.status_code == 201
    v1_data = resubmit_res.json()
    assert v1_data["submission_id"] == sub_id
    assert v1_data["resubmission_count"] == 1
    assert v1_data["file_name"] == "draft_v2.pdf"
    assert v1_data["submission_status"] == "SUBMITTED"
    assert v1_data["marks"] is None
    assert v1_data["feedback"] is None

    # 3. Case B: Teacher evaluates the newly resubmitted version (v1)
    grade_res_v1 = client.put(
        f"/api/submissions/{sub_id}/grade",
        json={"marks": 95.0, "feedback": "Great revisions on citations!"},
        headers={"Authorization": "Bearer valid-token-teacher-a"},
    )
    assert grade_res_v1.status_code == 200
    graded_v1 = grade_res_v1.json()
    assert graded_v1["submission_status"] == "GRADED"
    assert graded_v1["marks"] == 95.0
    assert graded_v1["resubmission_count"] == 1
    assert graded_v1["file_name"] == "draft_v2.pdf"


# ==============================================================================
# 3. ROLE CHANGE MID-SESSION: Live Firestore Reads vs Token Caching
# ==============================================================================
def test_role_change_mid_session_reads_current_firestore_role(client, mock_db):
    """
    Scenario 3: A user with an already-issued token has their Firestore role changed.
    Confirm get_current_user reads current Firestore role directly, without relying on stale claims.
    """
    # 1. User starts as STUDENT
    assert mock_db.users["student-uid-charlie"]["role"] == "STUDENT"

    # Student cannot create courses -> 403 Forbidden
    create_res = client.post(
        "/api/courses",
        json={"course_name": "CS999: Hacked Course", "description": "Attempted breach"},
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert create_res.status_code == 403

    # 2. Promote user to TEACHER in Firestore
    mock_db.users["student-uid-charlie"]["role"] = "TEACHER"

    # 3. With the EXACT SAME token, the next request must succeed because role is read from Firestore
    promote_res = client.post(
        "/api/courses",
        json={"course_name": "CS601: Advanced Cloud", "description": "Taught by newly promoted teacher"},
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert promote_res.status_code == 201
    assert promote_res.json()["teacher_id"] == "student-uid-charlie"

    # And now they cannot access student-only endpoints (e.g. submit)
    now = datetime.now(timezone.utc)
    mock_db.create_assignment(promote_res.json()["course_id"], "assign-promoted", {
        "title": "Task", "description": "Desc", "deadline": now + timedelta(days=1),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "student-uid-charlie",
    })
    sub_res = client.post(
        "/api/assignments/assign-promoted/submit",
        files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers={"Authorization": "Bearer valid-token-student-c"},
    )
    assert sub_res.status_code == 403


# ==============================================================================
# 4. CROSS-COURSE / CROSS-TEACHER BOUNDARY STRESS MATRIX
# ==============================================================================
def test_cross_teacher_security_boundary_matrix(client, mock_db):
    """
    Scenario 4: 2 Teachers (Teacher A and Teacher B), each with courses, assignments, and submissions.
    Run full matrix of Teacher A attempting to touch Teacher B's resources:
    All must return 403 Forbidden.
    """
    now = datetime.now(timezone.utc)

    # Course A (Teacher A)
    mock_db.create_course("course-a", {
        "course_name": "Course A", "teacher_id": "teacher-uid-a", "created_at": now,
    })
    mock_db.create_assignment("course-a", "assign-a", {
        "title": "Assignment A", "description": "A", "deadline": now + timedelta(days=3),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })
    mock_db.create_submission("sub-a", {
        "assignment_id": "assign-a", "course_id": "course-a", "student_id": "student-uid-charlie",
        "file_name": "a.pdf", "storage_path": "assignments/course-a/assign-a/student-uid-charlie/a.pdf",
        "submitted_at": now, "submission_status": "SUBMITTED", "resubmission_count": 0,
    })

    # Course B (Teacher B)
    mock_db.create_course("course-b", {
        "course_name": "Course B", "teacher_id": "teacher-uid-b", "created_at": now,
    })
    mock_db.create_assignment("course-b", "assign-b", {
        "title": "Assignment B", "description": "B", "deadline": now + timedelta(days=3),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "teacher-uid-b",
        "is_deleted": False,
    })
    mock_db.create_submission("sub-b", {
        "assignment_id": "assign-b", "course_id": "course-b", "student_id": "student-uid-dave",
        "file_name": "b.pdf", "storage_path": "assignments/course-b/assign-b/student-uid-dave/b.pdf",
        "submitted_at": now, "submission_status": "SUBMITTED", "resubmission_count": 0,
    })

    auth_a = {"Authorization": "Bearer valid-token-teacher-a"}

    # Matrix: Teacher A attempting operations on Course B / Assignment B / Submission B
    # 1. Create assignment in Course B
    r = client.post("/api/courses/course-b/assignments", json={
        "title": "Injected", "description": "Desc", "deadline": (now + timedelta(days=2)).isoformat(),
        "max_marks": 50, "allowed_file_types": "pdf", "max_file_size_mb": 5,
    }, headers=auth_a)
    assert r.status_code == 403

    # 2. Update Assignment B
    r = client.put("/api/courses/course-b/assignments/assign-b", json={"title": "Tampered"}, headers=auth_a)
    assert r.status_code == 403

    # 3. Delete Assignment B
    r = client.delete("/api/courses/course-b/assignments/assign-b", headers=auth_a)
    assert r.status_code == 403

    # 4. Delete Course B
    r = client.delete("/api/courses/course-b", headers=auth_a)
    assert r.status_code == 403

    # 5. List Submissions for Assignment B
    r = client.get("/api/assignments/assign-b/submissions", headers=auth_a)
    assert r.status_code == 403

    # 6. View single Submission B
    r = client.get("/api/submissions/sub-b", headers=auth_a)
    assert r.status_code == 403

    # 7. Download Submission B file
    r = client.get("/api/submissions/sub-b/download", headers=auth_a)
    assert r.status_code == 403

    # 8. Grade Submission B
    r = client.put("/api/submissions/sub-b/grade", json={"marks": 10.0, "feedback": "Unauthorized grade"}, headers=auth_a)
    assert r.status_code == 403

    # 9. View Gradebook Matrix for Assignment B
    r = client.get("/api/assignments/assign-b/grades", headers=auth_a)
    assert r.status_code == 403

    # 10. View Stats for Assignment B
    r = client.get("/api/assignments/assign-b/stats", headers=auth_a)
    assert r.status_code == 403


# ==============================================================================
# 5. DEADLINE EDGE CASES AT SCALE
# ==============================================================================
def test_deadline_edge_cases_end_to_end(client, mock_db):
    """
    Scenario 5: Test submission endpoint with deadlines:
    - Exactly at server time
    - 1 second before server time
    - 1 second after server time
    Tests both allow_late_submission=True and allow_late_submission=False.
    """
    now = datetime.now(timezone.utc)
    course_id = "course-deadlines"
    mock_db.create_course(course_id, {
        "course_name": "Deadline Testing Course", "teacher_id": "teacher-uid-a", "created_at": now,
    })

    # Assignment 1: Late submissions allowed
    mock_db.create_assignment(course_id, "assign-late-allowed", {
        "title": "Late Allowed", "description": "D", "deadline": now,
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })

    # Assignment 2: Strict deadline (Late submissions BLOCKED)
    mock_db.create_assignment(course_id, "assign-strict-past", {
        "title": "Strict Past", "description": "D", "deadline": now - timedelta(seconds=1),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": False, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })

    mock_db.create_assignment(course_id, "assign-strict-future", {
        "title": "Strict Future", "description": "D", "deadline": now + timedelta(seconds=10),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": False, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })

    auth_c = {"Authorization": "Bearer valid-token-student-c"}

    # Test 1: Late allowed, deadline is now or past -> Accepted with LATE status
    r = client.post(
        "/api/assignments/assign-late-allowed/submit",
        files={"file": ("sol.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers=auth_c,
    )
    assert r.status_code == 201
    assert r.json()["submission_status"] in ["SUBMITTED", "LATE"]

    # Test 2: Strict assignment 1 sec past deadline -> REJECTED with 400
    r = client.post(
        "/api/assignments/assign-strict-past/submit",
        files={"file": ("sol.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers=auth_c,
    )
    assert r.status_code == 400
    assert "not permitted" in r.json()["detail"].lower()

    # Test 3: Strict assignment 10 sec in future -> ACCEPTED with SUBMITTED status
    r = client.post(
        "/api/assignments/assign-strict-future/submit",
        files={"file": ("sol.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers=auth_c,
    )
    assert r.status_code == 201
    assert r.json()["submission_status"] == "SUBMITTED"


# ==============================================================================
# 6. STORAGE ORPHAN CHECK: Retention of Superseded Files
# ==============================================================================
def test_storage_orphan_retention_and_no_dangling_reference(client, mock_db, mock_storage):
    """
    Scenario 6: Confirm when a submission is resubmitted, the old file still exists
    in storage, and delete_file was never invoked on active submission files.
    """
    now = datetime.now(timezone.utc)
    course_id = "course-storage"
    assign_id = "assign-storage"

    mock_db.create_course(course_id, {
        "course_name": "Cloud Storage Course", "teacher_id": "teacher-uid-a", "created_at": now,
    })
    mock_db.create_assignment(course_id, assign_id, {
        "title": "Blob Test", "description": "Test", "deadline": now + timedelta(days=2),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })

    auth_c = {"Authorization": "Bearer valid-token-student-c"}

    # 1. First upload (v0)
    client.post(
        f"/api/assignments/{assign_id}/submit",
        files={"file": ("file_v0.pdf", io.BytesIO(b"version 0 content"), "application/pdf")},
        headers=auth_c,
    )
    assert len(mock_storage.uploaded_files) == 1
    v0_path = list(mock_storage.uploaded_files.keys())[0]

    # 2. Resubmission (v1)
    client.post(
        f"/api/assignments/{assign_id}/submit",
        files={"file": ("file_v1.pdf", io.BytesIO(b"version 1 content"), "application/pdf")},
        headers=auth_c,
    )
    assert len(mock_storage.uploaded_files) == 2
    v1_path = [p for p in mock_storage.uploaded_files.keys() if "file_v1.pdf" in p][0]

    # Verify both v0 and v1 exist in storage
    assert v0_path in mock_storage.uploaded_files
    assert v1_path in mock_storage.uploaded_files

    # Confirm delete_file was NEVER called on any submission file
    assert len(mock_storage.delete_calls) == 0

    # Confirm Firestore submission document points to active v1 file
    sub = mock_db.get_submission_by_student_and_assignment(assign_id, "student-uid-charlie")
    assert sub["storage_path"] == v1_path
    assert sub["file_name"] == "file_v1.pdf"


# ==============================================================================
# 7. EMPTY / BOUNDARY INPUT FUZZING
# ==============================================================================
def test_input_fuzzing_boundaries(client, mock_db):
    """
    Scenario 7: Fuzz create-course, create-assignment, submit, and grade endpoints with:
    - Empty strings, whitespace-only strings
    - Extremely long strings (10,000+ characters)
    - NaN, Infinity, and negative values
    Confirm consistent 400s or 422s, NEVER 500s.
    """
    auth_t = {"Authorization": "Bearer valid-token-teacher-a"}
    now = datetime.now(timezone.utc)

    # 1. Course Name Fuzzing
    # Whitespace only
    r = client.post("/api/courses", json={"course_name": "   ", "description": "spaces"}, headers=auth_t)
    assert r.status_code in [400, 422]

    # Extremely long course name (10,000 chars exceeds max_length=255)
    r = client.post("/api/courses", json={"course_name": "A" * 10000, "description": "long"}, headers=auth_t)
    assert r.status_code in [400, 422]

    # 2. Assignment Fuzzing
    mock_db.create_course("course-fuzz", {
        "course_name": "Fuzz Testing", "teacher_id": "teacher-uid-a", "created_at": now,
    })

    # Whitespace title
    r = client.post("/api/courses/course-fuzz/assignments", json={
        "title": "   ", "description": "Valid desc", "deadline": (now + timedelta(days=2)).isoformat(),
        "max_marks": 100, "allowed_file_types": "pdf", "max_file_size_mb": 10,
    }, headers=auth_t)
    assert r.status_code in [400, 422]

    # NaN max_marks
    r = client.post("/api/courses/course-fuzz/assignments", json={
        "title": "Fuzz NaN", "description": "Desc", "deadline": (now + timedelta(days=2)).isoformat(),
        "max_marks": "NaN", "allowed_file_types": "pdf", "max_file_size_mb": 10,
    }, headers=auth_t)
    assert r.status_code in [400, 422]

    # Infinity max_marks
    r = client.post("/api/courses/course-fuzz/assignments", json={
        "title": "Fuzz Inf", "description": "Desc", "deadline": (now + timedelta(days=2)).isoformat(),
        "max_marks": "Infinity", "allowed_file_types": "pdf", "max_file_size_mb": 10,
    }, headers=auth_t)
    assert r.status_code in [400, 422]

    # Negative max_marks
    r = client.post("/api/courses/course-fuzz/assignments", json={
        "title": "Fuzz Neg", "description": "Desc", "deadline": (now + timedelta(days=2)).isoformat(),
        "max_marks": -50, "allowed_file_types": "pdf", "max_file_size_mb": 10,
    }, headers=auth_t)
    assert r.status_code in [400, 422]

    # 3. Grading Fuzzing
    mock_db.create_assignment("course-fuzz", "assign-fuzz", {
        "title": "Grading Fuzz", "description": "Desc", "deadline": now + timedelta(days=2),
        "max_marks": 100.0, "allowed_file_types": "pdf", "max_file_size_mb": 10.0,
        "allow_late_submission": True, "resubmission_allowed": True, "created_by": "teacher-uid-a",
        "is_deleted": False,
    })
    mock_db.create_submission("sub-fuzz", {
        "assignment_id": "assign-fuzz", "course_id": "course-fuzz", "student_id": "student-uid-charlie",
        "file_name": "test.pdf", "file_url": "path/test.pdf", "storage_path": "path/test.pdf", "submitted_at": now,
        "submission_status": "SUBMITTED", "resubmission_count": 0,
    })

    # Grade with NaN
    r = client.put("/api/submissions/sub-fuzz/grade", json={"marks": "NaN", "feedback": "fuzz"}, headers=auth_t)
    assert r.status_code in [400, 422]

    # Grade with Infinity
    r = client.put("/api/submissions/sub-fuzz/grade", json={"marks": "Infinity", "feedback": "fuzz"}, headers=auth_t)
    assert r.status_code in [400, 422]

    # Grade exceeding max marks (e.g. 500 when max is 100)
    r = client.put("/api/submissions/sub-fuzz/grade", json={"marks": 500.0, "feedback": "over limit"}, headers=auth_t)
    assert r.status_code == 400

    # Grade with massive 10,000 char feedback (should handle safely without crashing)
    r = client.put("/api/submissions/sub-fuzz/grade", json={"marks": 90.0, "feedback": "Detailed feedback. " * 500}, headers=auth_t)
    assert r.status_code == 200
    assert r.json()["marks"] == 90.0
