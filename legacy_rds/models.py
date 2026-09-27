"""
SQLAlchemy Data Models for Cloud-Based Student Assignment Submission Portal.
"""
import uuid
import enum
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Uuid,
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class SubmissionStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    LATE = "LATE"
    GRADED = "GRADED"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(
        SQLEnum(UserRole, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.STUDENT,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    courses_taught = relationship(
        "Course",
        back_populates="teacher",
        foreign_keys="Course.teacher_id",
        cascade="all, delete-orphan",
    )
    assignments_created = relationship(
        "Assignment",
        back_populates="creator",
        foreign_keys="Assignment.created_by",
    )
    submissions = relationship(
        "Submission",
        back_populates="student",
        foreign_keys="Submission.student_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.name} ({self.role}) - {self.email}>"


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    course_name = Column(String(255), nullable=False)
    teacher_id = Column(Uuid, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    teacher = relationship(
        "User",
        back_populates="courses_taught",
        foreign_keys=[teacher_id],
    )
    assignments = relationship(
        "Assignment",
        back_populates="course",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Course {self.course_name}>"


class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    course_id = Column(Uuid, ForeignKey("courses.course_id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False)
    max_marks = Column(Float, nullable=False, default=100.0)
    allowed_file_types = Column(String(100), nullable=False, default="pdf,docx,zip")
    max_file_size_mb = Column(Float, nullable=False, default=10.0)
    created_by = Column(Uuid, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    course = relationship(
        "Course",
        back_populates="assignments",
        foreign_keys=[course_id],
    )
    creator = relationship(
        "User",
        back_populates="assignments_created",
        foreign_keys=[created_by],
    )
    submissions = relationship(
        "Submission",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Assignment {self.title}>"


class Submission(Base):
    __tablename__ = "submissions"

    submission_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    assignment_id = Column(Uuid, ForeignKey("assignments.assignment_id"), nullable=False)
    student_id = Column(Uuid, ForeignKey("users.user_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(1024), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    submission_status = Column(
        SQLEnum(SubmissionStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubmissionStatus.SUBMITTED,
    )
    marks = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assignment = relationship(
        "Assignment",
        back_populates="submissions",
        foreign_keys=[assignment_id],
    )
    student = relationship(
        "User",
        back_populates="submissions",
        foreign_keys=[student_id],
    )

    def __repr__(self) -> str:
        return f"<Submission {self.file_name} - Status: {self.submission_status}>"
