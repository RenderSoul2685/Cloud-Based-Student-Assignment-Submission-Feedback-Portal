"""
Firestore Domain Models and Enums for Assignment Submission & Feedback Portal.
"""
import enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class SubmissionStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    LATE = "LATE"
    GRADED = "GRADED"


# Document Path Constants
USERS_COLLECTION = "users"
COURSES_COLLECTION = "courses"
ASSIGNMENTS_SUBCOLLECTION = "assignments"
SUBMISSIONS_COLLECTION = "submissions"
