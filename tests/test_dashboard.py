"""
Automated Test Suite for Student and Teacher/Admin Aggregated Dashboards.
Verifies metrics aggregation, pending/overdue classification, upcoming deadlines,
recent grades, ungraded counts, assignments needing attention, recent activity feed,
RBAC security restrictions (403s), and zero/empty states for new accounts.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.models.schemas import UserRole, SubmissionStatus
from backend.app.routes.auth_routes import get_db_service as auth_get_db
from backend.app.routes.course_routes import get_db_service as course_get_db
from backend.app.routes.assignment_routes import get_db_service as assign_get_db
from backend.app.routes.submission_routes import (
    get_db_service as sub_get_db,
    get_storage_service as sub_get_storage,
)
from backend.app.routes.dashboard_routes import get_db_service as dash_get_db
from backend.app.middleware.auth_middleware import get_db_service as mw_get_db_service
from unittest.mock import patch
from tests.test_submissions import MockFirestoreDatabase, MockStorageService


@pytest.fixture
def dashboard_setup():
    mock_db = MockFirestoreDatabase()
    mock_storage = MockStorageService()

    app.dependency_overrides[auth_get_db] = lambda: mock_db
    app.dependency_overrides[course_get_db] = lambda: mock_db
    app.dependency_overrides[assign_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_db] = lambda: mock_db
    app.dependency_overrides[dash_get_db] = lambda: mock_db
    app.dependency_overrides[mw_get_db_service] = lambda: mock_db
    app.dependency_overrides[sub_get_storage] = lambda: mock_storage

    def mock_verify_token(token: str):
        token_map = {
            "token-teacher-smith": {"uid": "teacher-uid-smith", "email": "smith@portal.edu"},
            "token-teacher-jones": {"uid": "teacher-uid-jones", "email": "jones@portal.edu"},
            "token-student-alice": {"uid": "student-uid-alice", "email": "alice@portal.edu"},
            "token-student-bob": {"uid": "student-uid-bob", "email": "bob@portal.edu"},
            "token-admin-root": {"uid": "admin-uid-root", "email": "admin@portal.edu"},
            "token-new-student": {"uid": "new-student-uid", "email": "fresh@student.edu"},
            "token-new-teacher": {"uid": "new-teacher-uid", "email": "fresh@teacher.edu"},
        }
        if token in token_map:
            return token_map[token]
        raise ValueError("Invalid ID token")

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_verify_token):
        client = TestClient(app)
        yield client, mock_db, mock_storage

    app.dependency_overrides.clear()


def test_student_dashboard_metrics_and_feeds(dashboard_setup):
    """
    Test student dashboard metrics calculation:
    - total_courses: 2 seeded courses
    - assignments across courses
    - student submits 1 on-time, 1 graded, 1 overdue unsubmitted, 1 pending unsubmitted
    """
    client, mock_store, _ = dashboard_setup
    now = datetime.now(timezone.utc)
    student_id = "student-uid-alice"

    # Seed an on-time submission for Alice
    mock_store.submissions["sub-alice-1"] = {
        "assignment_id": "assign-on-time",
        "course_id": "course-cs501",
        "student_id": student_id,
        "file_name": "solution_v1.pdf",
        "file_url": "https://storage.googleapis.com/mock/solution_v1.pdf",
        "storage_path": "courses/course-cs501/assignments/assign-on-time/student-uid-alice/sub-1.pdf",
        "submitted_at": now - timedelta(hours=2),
        "submission_status": SubmissionStatus.SUBMITTED.value,
        "resubmission_count": 0,
        "marks": None,
        "feedback": None,
        "graded_at": None,
        "graded_by": None,
    }

    # Seed a graded submission for Alice in another assignment
    mock_store.submissions["sub-alice-2"] = {
        "assignment_id": "assign-late-allowed",
        "course_id": "course-cs501",
        "student_id": student_id,
        "file_name": "late_solution.pdf",
        "file_url": "https://storage.googleapis.com/mock/late_solution.pdf",
        "storage_path": "courses/course-cs501/assignments/assign-late-allowed/student-uid-alice/sub-2.pdf",
        "submitted_at": now - timedelta(days=1),
        "submission_status": SubmissionStatus.GRADED.value,
        "resubmission_count": 0,
        "marks": 92.0,
        "feedback": "Great analysis and code quality!",
        "graded_at": now - timedelta(hours=5),
        "graded_by": "teacher-uid-smith",
    }

    response = client.get(
        "/api/dashboard/student",
        headers={"Authorization": "Bearer token-student-alice"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_courses"] == 2
    assert data["total_assignments"] == 4  # assign-on-time, assign-late-allowed, assign-late-blocked, assign-no-resubmit
    assert data["submitted_count"] == 1
    assert data["graded_count"] == 1
    assert data["late_count"] == 0

    # Remaining unsubmitted assignments:
    # 1. assign-late-blocked (deadline past -> overdue)
    # 2. assign-no-resubmit (deadline future -> pending)
    assert data["pending_count"] == 1
    assert data["overdue_count"] == 1

    # Check upcoming unsubmitted deadlines list
    assert len(data["upcoming_deadlines"]) == 2
    assert any(u["assignment_id"] == "assign-no-resubmit" for u in data["upcoming_deadlines"])
    assert any(u["assignment_id"] == "assign-late-blocked" for u in data["upcoming_deadlines"])

    # Check recent grades
    assert len(data["recent_grades"]) == 1
    recent_grade = data["recent_grades"][0]
    assert recent_grade["submission_id"] == "sub-alice-2"
    assert recent_grade["marks"] == 92.0
    assert recent_grade["feedback"] == "Great analysis and code quality!"
    assert recent_grade["course_name"] == "CS501: Cloud Computing Architecture"


def test_teacher_dashboard_metrics_and_needs_attention(dashboard_setup):
    """
    Test teacher dashboard:
    - total_courses: 1 (course-cs501 for teacher-uid-smith)
    - total_assignments: 4
    - multiple submissions across assignments (some graded, some ungraded)
    - identifies assignment needing the most attention
    - recent submissions feed
    """
    client, mock_store, _ = dashboard_setup
    now = datetime.now(timezone.utc)
    teacher_id = "teacher-uid-smith"

    # Alice submits to assign-on-time (ungraded)
    mock_store.submissions["sub-1"] = {
        "assignment_id": "assign-on-time",
        "course_id": "course-cs501",
        "student_id": "student-uid-alice",
        "file_name": "alice_work.pdf",
        "file_url": "https://mock/alice.pdf",
        "storage_path": "path/alice.pdf",
        "submitted_at": now - timedelta(hours=3),
        "submission_status": SubmissionStatus.SUBMITTED.value,
        "resubmission_count": 0,
        "marks": None,
        "feedback": None,
    }

    # Bob submits to assign-on-time (ungraded)
    mock_store.submissions["sub-2"] = {
        "assignment_id": "assign-on-time",
        "course_id": "course-cs501",
        "student_id": "student-uid-bob",
        "file_name": "bob_work.pdf",
        "file_url": "https://mock/bob.pdf",
        "storage_path": "path/bob.pdf",
        "submitted_at": now - timedelta(hours=1),
        "submission_status": SubmissionStatus.LATE.value,
        "resubmission_count": 0,
        "marks": None,
        "feedback": None,
    }

    # Alice submits to assign-late-allowed and it's already graded
    mock_store.submissions["sub-3"] = {
        "assignment_id": "assign-late-allowed",
        "course_id": "course-cs501",
        "student_id": "student-uid-alice",
        "file_name": "alice_graded.pdf",
        "file_url": "https://mock/alice_graded.pdf",
        "storage_path": "path/alice_graded.pdf",
        "submitted_at": now - timedelta(days=2),
        "submission_status": SubmissionStatus.GRADED.value,
        "resubmission_count": 0,
        "marks": 95.0,
        "feedback": "Perfect!",
        "graded_at": now - timedelta(days=1),
        "graded_by": teacher_id,
    }

    response = client.get(
        "/api/dashboard/teacher",
        headers={"Authorization": "Bearer token-teacher-smith"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_courses"] == 1
    assert data["total_assignments"] == 4
    assert data["total_students"] == 2  # Alice and Bob
    assert data["ungraded_count"] == 2  # sub-1 and sub-2

    # Assignments needing attention
    assert len(data["assignments_needing_attention"]) >= 1
    top_attention = data["assignments_needing_attention"][0]
    assert top_attention["assignment_id"] == "assign-on-time"
    assert top_attention["ungraded_count"] == 2
    assert top_attention["total_submissions"] == 2

    # Recent submissions feed (most recent first)
    assert len(data["recent_submissions"]) == 3
    assert data["recent_submissions"][0]["submission_id"] == "sub-2"  # 1 hour ago
    assert data["recent_submissions"][1]["submission_id"] == "sub-1"  # 3 hours ago
    assert data["recent_submissions"][2]["submission_id"] == "sub-3"  # 2 days ago
    assert data["recent_submissions"][0]["student_name"] == "Bob Martin"


def test_student_cannot_access_teacher_dashboard(dashboard_setup):
    """Verify student role gets 403 when calling /api/dashboard/teacher."""
    client, _, _ = dashboard_setup
    response = client.get(
        "/api/dashboard/teacher",
        headers={"Authorization": "Bearer token-student-alice"},
    )
    assert response.status_code == 403


def test_teacher_cannot_access_student_dashboard(dashboard_setup):
    """Verify teacher role gets 403 when calling /api/dashboard/student."""
    client, _, _ = dashboard_setup
    response = client.get(
        "/api/dashboard/student",
        headers={"Authorization": "Bearer token-teacher-smith"},
    )
    assert response.status_code == 403


def test_empty_dashboard_for_new_users(dashboard_setup):
    """
    Verify fresh student and teacher with zero data return correct zero/empty structures
    without errors or unhandled exceptions.
    """
    client, mock_store, _ = dashboard_setup
    now = datetime.now(timezone.utc)
    # Register fresh student
    mock_store.users["new-student-uid"] = {
        "name": "Fresh Student",
        "email": "fresh@student.edu",
        "role": "STUDENT",
        "created_at": now,
    }
    # Register fresh teacher
    mock_store.users["new-teacher-uid"] = {
        "name": "Fresh Instructor",
        "email": "fresh@teacher.edu",
        "role": "TEACHER",
        "created_at": now,
    }

    # 1. Fresh Student (when no submissions exist)
    res_student = client.get(
        "/api/dashboard/student",
        headers={"Authorization": "Bearer token-new-student"},
    )
    assert res_student.status_code == 200
    stu_data = res_student.json()
    assert stu_data["submitted_count"] == 0
    assert stu_data["late_count"] == 0
    assert stu_data["graded_count"] == 0
    assert stu_data["recent_grades"] == []

    # 2. Fresh Teacher (no courses assigned)
    res_teacher = client.get(
        "/api/dashboard/teacher",
        headers={"Authorization": "Bearer token-new-teacher"},
    )
    assert res_teacher.status_code == 200
    teach_data = res_teacher.json()
    assert teach_data["total_courses"] == 0
    assert teach_data["total_assignments"] == 0
    assert teach_data["total_students"] == 0
    assert teach_data["ungraded_count"] == 0
    assert teach_data["assignments_needing_attention"] == []
    assert teach_data["recent_submissions"] == []


def test_admin_accesses_teacher_dashboard_sees_all_courses(dashboard_setup):
    """Verify admin role can access /api/dashboard/teacher and views all courses."""
    client, _, _ = dashboard_setup
    response = client.get(
        "/api/dashboard/teacher",
        headers={"Authorization": "Bearer token-admin-root"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_courses"] == 2  # Sees both CS501 and CS502
