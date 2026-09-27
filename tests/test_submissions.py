"""
Automated Test Suite for Student Assignment Submissions, Deadlines, and Grading.
Verifies on-time submissions, late submissions (allowed vs disallowed),
resubmissions (allowed vs disallowed, incrementing count), file validations,
RBAC security checks for viewing/downloading submissions,
teacher grading with score/feedback validation, gradebook views,
statistical evaluation metrics, and resubmission grade resets.
"""
import sys
import os
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
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
from backend.app.utils.deadline_utils import is_late, ensure_utc
from backend.app.utils.grading_stats import calculate_assignment_stats


class MockStorageService:
    """Mock Storage Service simulating Firebase Cloud Storage blob uploads and signed URLs."""
    def __init__(self):
        self.uploaded_files = {}  # storage_path -> bytes

    def upload_file(self, file_data, storage_path, content_type=None):
        if hasattr(file_data, "read"):
            data = file_data.read()
        else:
            data = file_data
        self.uploaded_files[storage_path] = data
        return storage_path

    def get_download_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        if storage_path in self.uploaded_files or True:
            return f"https://storage.googleapis.com/mock-bucket/{storage_path}?expires=3600"
        raise ValueError("Blob does not exist in storage")

    def delete_file(self, storage_path: str) -> bool:
        if storage_path in self.uploaded_files:
            del self.uploaded_files[storage_path]
            return True
        return False


class MockFirestoreDatabase:
    """In-memory Mock Firestore Database with Users, Courses, Assignments, and Submissions."""
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.users = {
            "teacher-uid-smith": {
                "name": "Dr. Robert Smith",
                "email": "smith@portal.edu",
                "role": "TEACHER",
                "created_at": now,
            },
            "teacher-uid-jones": {
                "name": "Prof. Sarah Jones",
                "email": "jones@portal.edu",
                "role": "TEACHER",
                "created_at": now,
            },
            "student-uid-alice": {
                "name": "Alice Johnson",
                "email": "alice@portal.edu",
                "role": "STUDENT",
                "created_at": now,
            },
            "student-uid-bob": {
                "name": "Bob Martin",
                "email": "bob@portal.edu",
                "role": "STUDENT",
                "created_at": now,
            },
            "admin-uid-root": {
                "name": "System Administrator",
                "email": "admin@portal.edu",
                "role": "ADMIN",
                "created_at": now,
            },
        }

        self.courses = {
            "course-cs501": {
                "course_name": "CS501: Cloud Computing Architecture",
                "description": "Distributed systems and cloud patterns",
                "teacher_id": "teacher-uid-smith",
                "created_at": now,
            },
            "course-cs502": {
                "course_name": "CS502: Advanced Database Systems",
                "description": "Distributed database indexing",
                "teacher_id": "teacher-uid-jones",
                "created_at": now,
            },
        }

        # Key: (course_id, assignment_id) -> data
        self.assignments = {
            ("course-cs501", "assign-on-time"): {
                "title": "Future Due Assignment",
                "description": "On-time submissions expected",
                "deadline": now + timedelta(days=7),
                "max_marks": 100.0,
                "allowed_file_types": "pdf,docx,zip",
                "max_file_size_mb": 10.0,
                "allow_late_submission": True,
                "resubmission_allowed": True,
                "created_by": "teacher-uid-smith",
                "created_at": now,
                "is_deleted": False,
                "deleted_at": None,
            },
            ("course-cs501", "assign-late-allowed"): {
                "title": "Past Due Assignment (Late Allowed)",
                "description": "Past deadline but allows late submission",
                "deadline": now - timedelta(days=2),
                "max_marks": 100.0,
                "allowed_file_types": "pdf,docx",
                "max_file_size_mb": 5.0,
                "allow_late_submission": True,
                "resubmission_allowed": True,
                "created_by": "teacher-uid-smith",
                "created_at": now,
                "is_deleted": False,
                "deleted_at": None,
            },
            ("course-cs501", "assign-late-blocked"): {
                "title": "Strict Past Due Assignment",
                "description": "Hard-blocks submissions past deadline",
                "deadline": now - timedelta(days=1),
                "max_marks": 50.0,
                "allowed_file_types": "pdf",
                "max_file_size_mb": 10.0,
                "allow_late_submission": False,
                "resubmission_allowed": True,
                "created_by": "teacher-uid-smith",
                "created_at": now,
                "is_deleted": False,
                "deleted_at": None,
            },
            ("course-cs501", "assign-no-resubmit"): {
                "title": "Single Attempt Exam Submission",
                "description": "Resubmissions are blocked",
                "deadline": now + timedelta(days=5),
                "max_marks": 100.0,
                "allowed_file_types": "pdf",
                "max_file_size_mb": 10.0,
                "allow_late_submission": True,
                "resubmission_allowed": False,
                "created_by": "teacher-uid-smith",
                "created_at": now,
                "is_deleted": False,
                "deleted_at": None,
            },
        }

        # Key: submission_id -> data
        self.submissions = {}

    def get_user(self, uid: str):
        if uid in self.users:
            return {"uid": uid, **self.users[uid]}
        return None

    def list_users(self, role=None):
        results = []
        for uid, udata in self.users.items():
            if not role or udata.get("role") == role:
                results.append({"uid": uid, **udata})
        return results

    def list_students(self):
        return self.list_users(role="STUDENT")

    def get_course(self, course_id: str):
        if course_id in self.courses:
            return {"course_id": course_id, **self.courses[course_id]}
        return None

    def list_courses(self):
        return [{"course_id": k, **v} for k, v in self.courses.items()]

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

    def list_assignments(self, course_id: str, include_deleted: bool = False):
        results = []
        for (c_id, a_id), data in self.assignments.items():
            if c_id == course_id:
                if not include_deleted and data.get("is_deleted") is True:
                    continue
                results.append({"assignment_id": a_id, "course_id": c_id, **data})
        return results

    def create_submission(self, submission_id: str, data: dict):
        self.submissions[submission_id] = data.copy()
        return {"submission_id": submission_id, **data}

    def get_submission(self, submission_id: str):
        if submission_id in self.submissions:
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None

    def get_submission_by_student_and_assignment(self, assignment_id: str, student_id: str):
        for s_id, data in self.submissions.items():
            if data.get("assignment_id") == assignment_id and data.get("student_id") == student_id:
                return {"submission_id": s_id, **data}
        return None

    def list_submissions_by_student(self, student_id: str):
        return [
            {"submission_id": s_id, **data}
            for s_id, data in self.submissions.items()
            if data.get("student_id") == student_id
        ]

    def list_submissions_by_assignment(self, assignment_id: str):
        return [
            {"submission_id": s_id, **data}
            for s_id, data in self.submissions.items()
            if data.get("assignment_id") == assignment_id
        ]

    def update_submission(self, submission_id: str, data: dict):
        if submission_id in self.submissions:
            self.submissions[submission_id].update(data)
            return {"submission_id": submission_id, **self.submissions[submission_id]}
        return None

    def has_submissions_for_assignment(self, course_id: str, assignment_id: str):
        for sub in self.submissions.values():
            if sub.get("assignment_id") == assignment_id:
                return True
        return False


@pytest.fixture
def sub_setup():
    mock_db = MockFirestoreDatabase()
    mock_storage = MockStorageService()

    app.dependency_overrides[auth_get_db] = lambda: mock_db
    app.dependency_overrides[course_get_db] = lambda: mock_db
    app.dependency_overrides[assign_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_db] = lambda: mock_db
    app.dependency_overrides[sub_get_storage] = lambda: mock_storage
    app.dependency_overrides[mw_get_db_service] = lambda: mock_db

    def mock_verify_token(token: str):
        token_map = {
            "token-teacher-smith": {"uid": "teacher-uid-smith", "email": "smith@portal.edu"},
            "token-teacher-jones": {"uid": "teacher-uid-jones", "email": "jones@portal.edu"},
            "token-student-alice": {"uid": "student-uid-alice", "email": "alice@portal.edu"},
            "token-student-bob": {"uid": "student-uid-bob", "email": "bob@portal.edu"},
            "token-admin-root": {"uid": "admin-uid-root", "email": "admin@portal.edu"},
        }
        if token in token_map:
            return token_map[token]
        raise ValueError("Invalid ID token")

    with patch("backend.app.middleware.auth_middleware.verify_firebase_token", side_effect=mock_verify_token):
        client = TestClient(app)
        yield client, mock_db, mock_storage

    app.dependency_overrides.clear()


# ==============================================================================
# 1. Direct Unit Tests for deadline_utils & grading_stats
# ==============================================================================
def test_is_late_exact_deadline_is_on_time():
    """Exact timestamp match must be on-time (False), not late."""
    dt = datetime(2026, 10, 15, 23, 59, 59, tzinfo=timezone.utc)
    assert is_late(dt, dt) is False


def test_is_late_before_deadline():
    """Submission prior to deadline is on-time."""
    deadline = datetime(2026, 10, 15, 23, 59, 59, tzinfo=timezone.utc)
    submitted = deadline - timedelta(seconds=1)
    assert is_late(submitted, deadline) is False


def test_is_late_after_deadline():
    """Submission 1 second after deadline is late."""
    deadline = datetime(2026, 10, 15, 23, 59, 59, tzinfo=timezone.utc)
    submitted = deadline + timedelta(seconds=1)
    assert is_late(submitted, deadline) is True


def test_is_late_with_different_timezones():
    """Timezones should be normalized to UTC accurately."""
    deadline_utc = datetime(2026, 10, 15, 18, 0, 0, tzinfo=timezone.utc)
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    submitted_ist = datetime(2026, 10, 15, 23, 30, 0, tzinfo=tz_ist)
    assert is_late(submitted_ist, deadline_utc) is False

    submitted_ist_late = datetime(2026, 10, 15, 23, 30, 1, tzinfo=tz_ist)
    assert is_late(submitted_ist_late, deadline_utc) is True


def test_is_late_with_naive_datetime():
    """Naive datetimes assume UTC and compare safely."""
    deadline = datetime(2026, 10, 15, 12, 0, 0)
    submitted = datetime(2026, 10, 15, 11, 59, 0)
    assert is_late(submitted, deadline) is False

    submitted_late = datetime(2026, 10, 15, 12, 1, 0)
    assert is_late(submitted_late, deadline) is True


def test_calculate_assignment_stats_direct():
    """Unit test for calculate_assignment_stats utility."""
    submissions = [
        {"submission_status": "GRADED", "marks": 85.0},
        {"submission_status": "GRADED", "marks": 95.0},
        {"submission_status": "GRADED", "marks": 70.0},
        {"submission_status": "SUBMITTED", "marks": None},
    ]
    stats = calculate_assignment_stats("assign-1", 100.0, submissions, total_students_count=6)
    assert stats["total_students"] == 6
    assert stats["total_submissions"] == 4
    assert stats["graded_count"] == 3
    assert stats["ungraded_count"] == 1
    assert stats["not_submitted_count"] == 2
    assert stats["average_marks"] == round((85.0 + 95.0 + 70.0) / 3, 2)
    assert stats["highest_marks"] == 95.0
    assert stats["lowest_marks"] == 70.0


# ==============================================================================
# 2. Student Submission Workflow Tests
# ==============================================================================
def test_on_time_submission_gets_status_submitted(sub_setup):
    """Student submitting before deadline gets status SUBMITTED."""
    client, mock_db, mock_storage = sub_setup

    file_content = b"%PDF-1.4 Mock PDF deliverable content"
    files = {"file": ("alice_assignment.pdf", io.BytesIO(file_content), "application/pdf")}

    res = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )

    assert res.status_code == 201
    data = res.json()
    assert data["submission_status"] == "SUBMITTED"
    assert data["student_id"] == "student-uid-alice"
    assert data["assignment_id"] == "assign-on-time"
    assert data["file_name"] == "alice_assignment.pdf"
    assert data["resubmission_count"] == 0
    assert len(mock_storage.uploaded_files) == 1


def test_past_deadline_submission_gets_status_late_when_allowed(sub_setup):
    """Past-deadline submission gets status LATE but is accepted when allow_late_submission is true."""
    client, mock_db, mock_storage = sub_setup

    file_content = b"%PDF-1.4 Late submission PDF"
    files = {"file": ("alice_late.pdf", io.BytesIO(file_content), "application/pdf")}

    res = client.post(
        "/api/assignments/assign-late-allowed/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )

    assert res.status_code == 201
    data = res.json()
    assert data["submission_status"] == "LATE"
    assert data["student_id"] == "student-uid-alice"
    assert data["resubmission_count"] == 0


def test_past_deadline_submission_rejected_when_allow_late_is_false(sub_setup):
    """Past-deadline submission is rejected with 400 when allow_late_submission is false."""
    client, mock_db, mock_storage = sub_setup

    file_content = b"%PDF-1.4 Blocked late PDF"
    files = {"file": ("alice_blocked.pdf", io.BytesIO(file_content), "application/pdf")}

    res = client.post(
        "/api/assignments/assign-late-blocked/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )

    assert res.status_code == 400
    data = res.json()
    assert "deadline" in data["detail"].lower()


def test_resubmission_increments_count_and_keeps_old_file(sub_setup):
    """Submitting again correctly resubmits (increments count, keeps old file in storage, updates record)."""
    client, mock_db, mock_storage = sub_setup

    # First submission
    files1 = {"file": ("alice_v1.pdf", io.BytesIO(b"Version 1"), "application/pdf")}
    res1 = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files1,
    )
    assert res1.status_code == 201
    sub_id = res1.json()["submission_id"]
    assert res1.json()["resubmission_count"] == 0
    assert len(mock_storage.uploaded_files) == 1
    v1_storage_path = list(mock_storage.uploaded_files.keys())[0]

    # Second submission (Resubmission)
    files2 = {"file": ("alice_v2.pdf", io.BytesIO(b"Version 2 updated"), "application/pdf")}
    res2 = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files2,
    )
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["submission_id"] == sub_id
    assert data2["file_name"] == "alice_v2.pdf"
    assert data2["resubmission_count"] == 1
    assert len(mock_storage.uploaded_files) == 2
    assert v1_storage_path in mock_storage.uploaded_files


def test_resubmission_rejected_when_resubmission_allowed_is_false(sub_setup):
    """Resubmission is rejected with 400 when resubmission_allowed is false."""
    client, mock_db, mock_storage = sub_setup

    files1 = {"file": ("alice_exam_v1.pdf", io.BytesIO(b"Exam attempt 1"), "application/pdf")}
    res1 = client.post(
        "/api/assignments/assign-no-resubmit/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files1,
    )
    assert res1.status_code == 201

    files2 = {"file": ("alice_exam_v2.pdf", io.BytesIO(b"Exam attempt 2"), "application/pdf")}
    res2 = client.post(
        "/api/assignments/assign-no-resubmit/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files2,
    )
    assert res2.status_code == 400
    assert "resubmissions" in res2.json()["detail"].lower()


def test_file_validation_disallowed_type_rejected(sub_setup):
    """Files with disallowed extensions are rejected."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("script.exe", io.BytesIO(b"malicious content"), "application/x-msdownload")}
    res = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    assert res.status_code == 400
    assert "not permitted" in res.json()["detail"]


# ==============================================================================
# 3. RBAC & Access Control Tests
# ==============================================================================
def test_student_cannot_view_or_download_other_students_submission(sub_setup):
    """A student cannot view or download another student's submission (403)."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("alice_work.pdf", io.BytesIO(b"Alice answers"), "application/pdf")}
    res_submit = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    assert res_submit.status_code == 201
    sub_id = res_submit.json()["submission_id"]

    res_get = client.get(
        f"/api/submissions/{sub_id}",
        headers={"Authorization": "Bearer token-student-bob"},
    )
    assert res_get.status_code == 403

    res_dl = client.get(
        f"/api/submissions/{sub_id}/download",
        headers={"Authorization": "Bearer token-student-bob"},
    )
    assert res_dl.status_code == 403


def test_teacher_cannot_view_submissions_for_other_teachers_course(sub_setup):
    """A teacher cannot view submissions for another teacher's course's assignment (403)."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("alice_cs501.pdf", io.BytesIO(b"CS501 content"), "application/pdf")}
    res_submit = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    assert res_submit.status_code == 201
    sub_id = res_submit.json()["submission_id"]

    res_jones_list = client.get(
        "/api/assignments/assign-on-time/submissions",
        headers={"Authorization": "Bearer token-teacher-jones"},
    )
    assert res_jones_list.status_code == 403


# ==============================================================================
# 4. Grading & Feedback Tests
# ==============================================================================
def test_teacher_grades_submission_success(sub_setup):
    """A teacher can grade a submission within their own course; marks/feedback/graded_at/graded_by are recorded."""
    client, mock_db, mock_storage = sub_setup

    # Student submits
    files = {"file": ("alice_report.pdf", io.BytesIO(b"Report content"), "application/pdf")}
    res_sub = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    assert res_sub.status_code == 201
    sub_id = res_sub.json()["submission_id"]

    # Teacher grades submission
    grade_payload = {
        "marks": 94.5,
        "feedback": "Outstanding analysis of distributed storage consensus and blob syncing.",
    }
    res_grade = client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json=grade_payload,
    )

    assert res_grade.status_code == 200
    data = res_grade.json()
    assert data["submission_status"] == "GRADED"
    assert data["marks"] == 94.5
    assert data["feedback"] == "Outstanding analysis of distributed storage consensus and blob syncing."
    assert data["graded_by"] == "teacher-uid-smith"
    assert data["graded_at"] is not None


def test_grading_invalid_marks_rejected(sub_setup):
    """Grading with marks > max_marks or marks < 0 is rejected with 400."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("alice_report.pdf", io.BytesIO(b"Report content"), "application/pdf")}
    res_sub = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    sub_id = res_sub.json()["submission_id"]

    # Max marks is 100.0, attempt to award 105.0 -> 400
    res_high = client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json={"marks": 105.0, "feedback": "Exceeds max"},
    )
    assert res_high.status_code == 400
    assert "between 0 and" in res_high.json()["detail"].lower()

    # Negative marks -> 422 or 400
    res_neg = client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json={"marks": -5.0, "feedback": "Negative score"},
    )
    assert res_neg.status_code in [400, 422]


def test_teacher_cannot_grade_submission_from_other_course(sub_setup):
    """A teacher cannot grade a submission from another teacher's course (403)."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("alice_report.pdf", io.BytesIO(b"Report content"), "application/pdf")}
    res_sub = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    sub_id = res_sub.json()["submission_id"]

    # Prof. Jones is instructor for CS502, not CS501
    res_grade = client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-jones"},
        json={"marks": 90.0, "feedback": "Unauthorized grading attempt"},
    )
    assert res_grade.status_code == 403


def test_student_cannot_access_grade_endpoint(sub_setup):
    """A student cannot access the grade endpoint at all (403)."""
    client, mock_db, mock_storage = sub_setup

    files = {"file": ("alice_report.pdf", io.BytesIO(b"Report content"), "application/pdf")}
    res_sub = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    sub_id = res_sub.json()["submission_id"]

    res_grade = client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-student-alice"},
        json={"marks": 100.0, "feedback": "Self grading"},
    )
    assert res_grade.status_code == 403


def test_resubmission_resets_graded_status_and_clears_marks(sub_setup):
    """Resubmitting a previously-graded submission clears marks/feedback/graded_at and resets status."""
    client, mock_db, mock_storage = sub_setup

    # 1. Initial submission
    files1 = {"file": ("alice_v1.pdf", io.BytesIO(b"Draft v1"), "application/pdf")}
    res_sub1 = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files1,
    )
    sub_id = res_sub1.json()["submission_id"]

    # 2. Teacher grades it
    client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json={"marks": 75.0, "feedback": "Initial feedback: good but needs more details."},
    )
    graded_doc = mock_db.get_submission(sub_id)
    assert graded_doc["submission_status"] == "GRADED"
    assert graded_doc["marks"] == 75.0

    # 3. Student resubmits with updated file
    files2 = {"file": ("alice_v2_improved.pdf", io.BytesIO(b"Updated complete version"), "application/pdf")}
    res_sub2 = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files2,
    )
    assert res_sub2.status_code == 201
    resub_data = res_sub2.json()

    # Status must be reset away from GRADED to SUBMITTED
    assert resub_data["submission_status"] == "SUBMITTED"
    assert resub_data["marks"] is None
    assert resub_data["feedback"] is None
    assert resub_data["graded_at"] is None
    assert resub_data["resubmission_count"] == 1


def test_gradebook_includes_all_students_and_not_submitted(sub_setup):
    """The gradebook endpoint correctly includes non-submitters as NOT_SUBMITTED."""
    client, mock_db, mock_storage = sub_setup

    # Alice submits to assign-on-time, Bob does not submit
    files = {"file": ("alice_hw.pdf", io.BytesIO(b"HW content"), "application/pdf")}
    res_sub = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files,
    )
    sub_id = res_sub.json()["submission_id"]

    # Grade Alice's submission
    client.put(
        f"/api/submissions/{sub_id}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json={"marks": 88.0, "feedback": "Well done"},
    )

    # Fetch gradebook
    res_gb = client.get(
        "/api/assignments/assign-on-time/grades",
        headers={"Authorization": "Bearer token-teacher-smith"},
    )
    assert res_gb.status_code == 200
    entries = res_gb.json()

    # Both Alice and Bob must appear
    alice_entry = next((e for e in entries if e["student_id"] == "student-uid-alice"), None)
    bob_entry = next((e for e in entries if e["student_id"] == "student-uid-bob"), None)

    assert alice_entry is not None
    assert alice_entry["submission_status"] == "GRADED"
    assert alice_entry["marks"] == 88.0

    assert bob_entry is not None
    assert bob_entry["submission_status"] == "NOT_SUBMITTED"
    assert bob_entry["marks"] is None
    assert bob_entry["submission_id"] is None


def test_assignment_stats_metrics(sub_setup):
    """The stats endpoint returns correct average/highest/lowest given a mix of graded and ungraded submissions."""
    client, mock_db, mock_storage = sub_setup

    # Alice submits and gets graded 90
    files_a = {"file": ("alice_hw.pdf", io.BytesIO(b"HW content"), "application/pdf")}
    res_a = client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-alice"},
        files=files_a,
    )
    client.put(
        f"/api/submissions/{res_a.json()['submission_id']}/grade",
        headers={"Authorization": "Bearer token-teacher-smith"},
        json={"marks": 90.0, "feedback": "Great"},
    )

    # Bob submits and remains ungraded
    files_b = {"file": ("bob_hw.pdf", io.BytesIO(b"Bob HW"), "application/pdf")}
    client.post(
        "/api/assignments/assign-on-time/submit",
        headers={"Authorization": "Bearer token-student-bob"},
        files=files_b,
    )

    # Fetch stats
    res_stats = client.get(
        "/api/assignments/assign-on-time/stats",
        headers={"Authorization": "Bearer token-teacher-smith"},
    )
    assert res_stats.status_code == 200
    stats = res_stats.json()

    assert stats["total_students"] == 2
    assert stats["total_submissions"] == 2
    assert stats["graded_count"] == 1
    assert stats["ungraded_count"] == 1
    assert stats["not_submitted_count"] == 0
    assert stats["average_marks"] == 90.0
    assert stats["highest_marks"] == 90.0
    assert stats["lowest_marks"] == 90.0
    assert stats["max_marks"] == 100.0
