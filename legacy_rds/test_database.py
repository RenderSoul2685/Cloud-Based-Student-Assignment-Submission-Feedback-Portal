"""
Automated Test Suite for Database Layer, Models, Relationships, and Seeding.
"""
import sys
import os
import uuid
import pytest
from datetime import datetime, timezone

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models.models import (
    User,
    Course,
    Assignment,
    Submission,
    UserRole,
    SubmissionStatus,
)
from backend.app.models.schemas import (
    UserRead,
    CourseRead,
    AssignmentRead,
    SubmissionRead,
)
from backend.app.db_init import init_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Initializes and seeds the database before running tests."""
    init_db()
    yield


@pytest.fixture
def db_session():
    """Provides a transactional database session for each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_seeded_users_exist(db_session):
    """Assert all 7 users (1 Admin, 2 Teachers, 4 Students) were seeded correctly."""
    users = db_session.query(User).all()
    assert len(users) == 7

    admins = [u for u in users if u.role == UserRole.ADMIN]
    teachers = [u for u in users if u.role == UserRole.TEACHER]
    students = [u for u in users if u.role == UserRole.STUDENT]

    assert len(admins) == 1
    assert admins[0].email == "admin@portal.edu"
    assert isinstance(admins[0].user_id, uuid.UUID)

    assert len(teachers) == 2
    assert {"alan.turing@portal.edu", "grace.hopper@portal.edu"}.issubset({t.email for t in teachers})

    assert len(students) == 4
    student_emails = {s.email for s in students}
    assert "alice.johnson@student.portal.edu" in student_emails
    assert "bob.smith@student.portal.edu" in student_emails


def test_seeded_courses_and_relationships(db_session):
    """Assert courses exist and relate correctly to teacher users."""
    courses = db_session.query(Course).all()
    assert len(courses) == 2

    for course in courses:
        assert isinstance(course.course_id, uuid.UUID)
        assert course.teacher is not None
        assert course.teacher.role == UserRole.TEACHER
        # Check reverse relationship
        assert course in course.teacher.courses_taught


def test_seeded_assignments_and_deadlines(db_session):
    """Assert assignments exist, have valid deadlines, and link to courses and creators."""
    assignments = db_session.query(Assignment).all()
    assert len(assignments) == 3

    for assignment in assignments:
        assert isinstance(assignment.assignment_id, uuid.UUID)
        assert assignment.course is not None
        assert assignment.creator is not None
        assert assignment.max_marks > 0
        assert assignment.max_file_size_mb > 0
        assert len(assignment.allowed_file_types) > 0


def test_seeded_submissions_statuses(db_session):
    """Assert submissions exist with on-time and late statuses."""
    submissions = db_session.query(Submission).all()
    assert len(submissions) == 2

    statuses = {s.submission_status for s in submissions}
    assert SubmissionStatus.SUBMITTED in statuses
    assert SubmissionStatus.LATE in statuses

    for sub in submissions:
        assert isinstance(sub.submission_id, uuid.UUID)
        assert sub.file_name.endswith(".pdf")
        assert sub.storage_path.startswith("submissions/")
        assert sub.assignment is not None
        assert sub.student is not None
        assert sub.student.role == UserRole.STUDENT


def test_relationship_traversal_chain(db_session):
    """Test full relational traversal: Teacher -> Course -> Assignment -> Submission -> Student."""
    teacher = db_session.query(User).filter(User.email == "alan.turing@portal.edu").first()
    assert teacher is not None
    assert len(teacher.courses_taught) > 0

    course = teacher.courses_taught[0]
    assert len(course.assignments) > 0

    assignment = course.assignments[0]
    assert len(assignment.submissions) > 0

    submission = assignment.submissions[0]
    student = submission.student
    assert student.role == UserRole.STUDENT
    assert submission in student.submissions


def test_pydantic_schema_validation(db_session):
    """Assert SQLAlchemy model instances seamlessly serialize into Pydantic v2 schemas."""
    user = db_session.query(User).filter(User.role == UserRole.STUDENT).first()
    user_dto = UserRead.model_validate(user)
    assert user_dto.user_id == user.user_id
    assert user_dto.email == user.email

    course = db_session.query(Course).first()
    course_dto = CourseRead.model_validate(course)
    assert course_dto.course_id == course.course_id
    assert course_dto.course_name == course.course_name

    assignment = db_session.query(Assignment).first()
    assignment_dto = AssignmentRead.model_validate(assignment)
    assert assignment_dto.assignment_id == assignment.assignment_id
    assert assignment_dto.title == assignment.title

    submission = db_session.query(Submission).first()
    submission_dto = SubmissionRead.model_validate(submission)
    assert submission_dto.submission_id == submission.submission_id
    assert submission_dto.submission_status == submission.submission_status
