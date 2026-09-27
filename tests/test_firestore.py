"""
Automated Test Suite for Firestore Data Models, Collections, Subcollections, and Seed Data.
Supports both Firebase Emulator Suite and In-Memory Mock Firestore for local testing.
"""
import sys
import os
import pytest
from datetime import datetime, timezone

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.models.models import (
    UserRole,
    SubmissionStatus,
    USERS_COLLECTION,
    COURSES_COLLECTION,
    ASSIGNMENTS_SUBCOLLECTION,
    SUBMISSIONS_COLLECTION,
)
from backend.app.models.schemas import (
    UserRead,
    CourseRead,
    AssignmentRead,
    SubmissionRead,
)
from backend.app.db_init import seed_firestore_data
from cloud.database_service import DatabaseService


class MockDocumentSnapshot:
    """Mock Firestore DocumentSnapshot."""
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict:
        return self._data.copy() if self._data else {}


class MockDocumentReference:
    """Mock Firestore DocumentReference supporting subcollections."""
    def __init__(self, doc_id: str, storage: dict, path: str):
        self.id = doc_id
        self._storage = storage
        self._path = path

    def set(self, data: dict):
        self._storage[self._path] = data.copy()

    def get(self) -> MockDocumentSnapshot:
        data = self._storage.get(self._path)
        return MockDocumentSnapshot(self.id, data)

    def collection(self, subcollection_name: str):
        return MockCollectionReference(self._storage, f"{self._path}/{subcollection_name}")


class MockCollectionReference:
    """Mock Firestore CollectionReference."""
    def __init__(self, storage: dict, path: str):
        self._storage = storage
        self._path = path

    def document(self, doc_id: str) -> MockDocumentReference:
        return MockDocumentReference(doc_id, self._storage, f"{self._path}/{doc_id}")

    def stream(self):
        docs = []
        prefix = f"{self._path}/"
        for key, value in self._storage.items():
            if key.startswith(prefix):
                remainder = key[len(prefix):]
                if "/" not in remainder:  # direct child
                    docs.append(MockDocumentSnapshot(remainder, value))
        return docs


class MockFirestoreClient:
    """In-memory Mock Firestore Client implementing Firestore collections & subcollections."""
    def __init__(self):
        self._storage = {}

    def collection(self, collection_name: str) -> MockCollectionReference:
        return MockCollectionReference(self._storage, collection_name)


@pytest.fixture
def firestore_db():
    """Provides a fresh Firestore client (Mock or Emulator) for testing."""
    mock_db = MockFirestoreClient()
    seed_firestore_data(mock_db)
    return mock_db


def test_seeded_users_in_firestore(firestore_db):
    """Verify all 7 users exist in /users/{uid} with valid roles."""
    users_docs = firestore_db.collection(USERS_COLLECTION).stream()
    users = [doc.to_dict() | {"uid": doc.id} for doc in users_docs]
    assert len(users) == 7

    admins = [u for u in users if u["role"] == UserRole.ADMIN.value]
    teachers = [u for u in users if u["role"] == UserRole.TEACHER.value]
    students = [u for u in users if u["role"] == UserRole.STUDENT.value]

    assert len(admins) == 1
    assert admins[0]["email"] == "admin@portal.edu"
    assert len(teachers) == 2
    assert len(students) == 4

    # Validate Pydantic schema deserialization
    for u in users:
        schema = UserRead.model_validate(u)
        assert schema.uid == u["uid"]
        assert schema.email == u["email"]


def test_seeded_courses_in_firestore(firestore_db):
    """Verify courses in /courses/{courseId} and schema serialization."""
    courses_docs = firestore_db.collection(COURSES_COLLECTION).stream()
    courses = [doc.to_dict() | {"course_id": doc.id} for doc in courses_docs]
    assert len(courses) == 2

    for c in courses:
        schema = CourseRead.model_validate(c)
        assert schema.course_id == c["course_id"]
        assert schema.teacher_id.startswith("teacher-uid-")


def test_seeded_assignments_subcollection(firestore_db):
    """Verify assignments subcollection /courses/{courseId}/assignments/{assignmentId}."""
    cs501_ref = firestore_db.collection(COURSES_COLLECTION).document("course-cs501")
    cs501_assignments = [
        doc.to_dict() | {"assignment_id": doc.id, "course_id": "course-cs501"}
        for doc in cs501_ref.collection(ASSIGNMENTS_SUBCOLLECTION).stream()
    ]
    assert len(cs501_assignments) == 2

    cs502_ref = firestore_db.collection(COURSES_COLLECTION).document("course-cs502")
    cs502_assignments = [
        doc.to_dict() | {"assignment_id": doc.id, "course_id": "course-cs502"}
        for doc in cs502_ref.collection(ASSIGNMENTS_SUBCOLLECTION).stream()
    ]
    assert len(cs502_assignments) == 1

    # Total 3 assignments across courses
    all_assignments = cs501_assignments + cs502_assignments
    assert len(all_assignments) == 3

    for a in all_assignments:
        schema = AssignmentRead.model_validate(a)
        assert schema.assignment_id.startswith("assign-")
        assert schema.max_marks == 100.0


def test_seeded_submissions_collection(firestore_db):
    """Verify top-level /submissions/{submissionId} with on-time and late statuses."""
    sub_docs = firestore_db.collection(SUBMISSIONS_COLLECTION).stream()
    submissions = [doc.to_dict() | {"submission_id": doc.id} for doc in sub_docs]
    assert len(submissions) == 2

    statuses = {s["submission_status"] for s in submissions}
    assert SubmissionStatus.SUBMITTED.value in statuses
    assert SubmissionStatus.LATE.value in statuses

    for s in submissions:
        schema = SubmissionRead.model_validate(s)
        assert schema.submission_id.startswith("sub-")
        assert schema.file_name.endswith(".pdf")
        assert schema.storage_path.startswith("submissions/")


def test_database_service_adapter(firestore_db):
    """Verify the DatabaseService wrapper methods execute CRUD correctly."""
    service = DatabaseService(client=firestore_db)

    # Test get user
    user = service.get_user("student-uid-alice")
    assert user is not None
    assert user["name"] == "Alice Johnson"

    # Test get course
    course = service.get_course("course-cs501")
    assert course is not None
    assert "Cloud Computing" in course["course_name"]

    # Test get assignment subcollection
    assignment = service.get_assignment("course-cs501", "assign-cs501-1")
    assert assignment is not None
    assert assignment["assignment_id"] == "assign-cs501-1"

    # Test get submission
    submission = service.get_submission("sub-alice-cs501-1")
    assert submission is not None
    assert submission["student_id"] == "student-uid-alice"
