"""
Firestore Database Initialization and Dummy Data Seeding Script.
Creates documents in Firestore for Users, Courses, Assignments, and Submissions.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from google.cloud.firestore import Client as FirestoreClient
from backend.app.firebase_config import get_firestore_client
from backend.app.models.models import (
    UserRole,
    SubmissionStatus,
    USERS_COLLECTION,
    COURSES_COLLECTION,
    ASSIGNMENTS_SUBCOLLECTION,
    SUBMISSIONS_COLLECTION,
)


def seed_firestore_data(db: Optional[FirestoreClient] = None) -> Dict[str, Any]:
    """
    Seeds initial dummy data into Firestore collections.
    Returns a summary dictionary of seeded records.
    """
    if db is None:
        db = get_firestore_client()

    now = datetime.now(timezone.utc)
    print("[FIRESTORE SEED] Starting Firestore seed process...")

    # --------------------------------------------------------------------------
    # 1. Seed Users (/users/{uid})
    # --------------------------------------------------------------------------
    print("[FIRESTORE SEED] Seeding Users...")
    users_data = [
        {
            "uid": "admin-uid-001",
            "name": "System Administrator",
            "email": "admin@portal.edu",
            "role": UserRole.ADMIN.value,
            "created_at": now - timedelta(days=30),
        },
        {
            "uid": "teacher-uid-alan",
            "name": "Prof. Alan Turing",
            "email": "alan.turing@portal.edu",
            "role": UserRole.TEACHER.value,
            "created_at": now - timedelta(days=25),
        },
        {
            "uid": "teacher-uid-grace",
            "name": "Dr. Grace Hopper",
            "email": "grace.hopper@portal.edu",
            "role": UserRole.TEACHER.value,
            "created_at": now - timedelta(days=20),
        },
        {
            "uid": "student-uid-alice",
            "name": "Alice Johnson",
            "email": "alice.johnson@student.portal.edu",
            "role": UserRole.STUDENT.value,
            "created_at": now - timedelta(days=15),
        },
        {
            "uid": "student-uid-bob",
            "name": "Bob Smith",
            "email": "bob.smith@student.portal.edu",
            "role": UserRole.STUDENT.value,
            "created_at": now - timedelta(days=14),
        },
        {
            "uid": "student-uid-charlie",
            "name": "Charlie Davis",
            "email": "charlie.davis@student.portal.edu",
            "role": UserRole.STUDENT.value,
            "created_at": now - timedelta(days=12),
        },
        {
            "uid": "student-uid-diana",
            "name": "Diana Prince",
            "email": "diana.prince@student.portal.edu",
            "role": UserRole.STUDENT.value,
            "created_at": now - timedelta(days=10),
        },
    ]

    for user in users_data:
        uid = user["uid"]
        doc_data = {k: v for k, v in user.items() if k != "uid"}
        db.collection(USERS_COLLECTION).document(uid).set(doc_data)

    # --------------------------------------------------------------------------
    # 2. Seed Courses (/courses/{courseId})
    # --------------------------------------------------------------------------
    print("[FIRESTORE SEED] Seeding Courses...")
    courses_data = [
        {
            "course_id": "course-cs501",
            "course_name": "CS501: Cloud Computing Architectures",
            "teacher_id": "teacher-uid-alan",
            "created_at": now - timedelta(days=18),
        },
        {
            "course_id": "course-cs502",
            "course_name": "CS502: Distributed Database Systems",
            "teacher_id": "teacher-uid-grace",
            "created_at": now - timedelta(days=15),
        },
    ]

    for course in courses_data:
        cid = course["course_id"]
        doc_data = {k: v for k, v in course.items() if k != "course_id"}
        db.collection(COURSES_COLLECTION).document(cid).set(doc_data)

    # --------------------------------------------------------------------------
    # 3. Seed Assignments (/courses/{courseId}/assignments/{assignmentId})
    # --------------------------------------------------------------------------
    print("[FIRESTORE SEED] Seeding Assignments Subcollections...")
    assignments_data = [
        {
            "course_id": "course-cs501",
            "assignment_id": "assign-cs501-1",
            "title": "Assignment 1: Firebase Architecture & NoSQL Design",
            "description": "Design a serverless assignment submission portal using Firestore subcollections and Firebase Storage.",
            "deadline": now + timedelta(days=7),  # Active future deadline
            "max_marks": 100.0,
            "allowed_file_types": "pdf,docx,zip",
            "max_file_size_mb": 25.0,
            "created_by": "teacher-uid-alan",
            "created_at": now - timedelta(days=5),
        },
        {
            "course_id": "course-cs501",
            "assignment_id": "assign-cs501-2",
            "title": "Assignment 2: Cloud Functions & Security Rules",
            "description": "Implement Firestore security rules preventing unauthorized student grade modifications.",
            "deadline": now + timedelta(days=14),  # Active future deadline
            "max_marks": 100.0,
            "allowed_file_types": "zip,pdf",
            "max_file_size_mb": 50.0,
            "created_by": "teacher-uid-alan",
            "created_at": now - timedelta(days=3),
        },
        {
            "course_id": "course-cs502",
            "assignment_id": "assign-cs502-1",
            "title": "Assignment 1: Distributed Consensus & CAP Theorem",
            "description": "Analyze event-driven replication and ACID vs BASE tradeoffs in distributed databases.",
            "deadline": now - timedelta(days=2),  # Past deadline to test late submission status
            "max_marks": 100.0,
            "allowed_file_types": "pdf,docx",
            "max_file_size_mb": 15.0,
            "created_by": "teacher-uid-grace",
            "created_at": now - timedelta(days=10),
        },
    ]

    for assignment in assignments_data:
        cid = assignment["course_id"]
        aid = assignment["assignment_id"]
        doc_data = {k: v for k, v in assignment.items() if k not in ("course_id", "assignment_id")}
        db.collection(COURSES_COLLECTION).document(cid).collection(ASSIGNMENTS_SUBCOLLECTION).document(aid).set(doc_data)

    # --------------------------------------------------------------------------
    # 4. Seed Submissions (/submissions/{submissionId})
    # --------------------------------------------------------------------------
    print("[FIRESTORE SEED] Seeding Submissions...")
    submissions_data = [
        {
            "submission_id": "sub-alice-cs501-1",
            "assignment_id": "assign-cs501-1",
            "course_id": "course-cs501",
            "student_id": "student-uid-alice",
            "file_name": "alice_firebase_architecture.pdf",
            "file_url": "https://firebasestorage.googleapis.com/v0/b/demo-bucket/o/submissions%2Fcs501%2Falice.pdf?alt=media",
            "storage_path": "submissions/course-cs501/assign-cs501-1/student-uid-alice/alice_firebase_architecture.pdf",
            "submitted_at": now - timedelta(days=1),
            "submission_status": SubmissionStatus.SUBMITTED.value,
            "marks": None,
            "feedback": None,
            "graded_at": None,
        },
        {
            "submission_id": "sub-bob-cs502-1",
            "assignment_id": "assign-cs502-1",
            "course_id": "course-cs502",
            "student_id": "student-uid-bob",
            "file_name": "bob_distributed_consensus.pdf",
            "file_url": "https://firebasestorage.googleapis.com/v0/b/demo-bucket/o/submissions%2Fcs502%2Fbob.pdf?alt=media",
            "storage_path": "submissions/course-cs502/assign-cs502-1/student-uid-bob/bob_distributed_consensus.pdf",
            "submitted_at": now - timedelta(hours=3),  # Submitted after past deadline
            "submission_status": SubmissionStatus.LATE.value,
            "marks": None,
            "feedback": None,
            "graded_at": None,
        },
    ]

    for submission in submissions_data:
        sid = submission["submission_id"]
        doc_data = {k: v for k, v in submission.items() if k != "submission_id"}
        db.collection(SUBMISSIONS_COLLECTION).document(sid).set(doc_data)

    print("[FIRESTORE SEED] Firestore seed finished successfully:")
    print(f"   * Users seeded: {len(users_data)} (1 Admin, 2 Teachers, 4 Students)")
    print(f"   * Courses seeded: {len(courses_data)}")
    print(f"   * Assignments seeded: {len(assignments_data)}")
    print(f"   * Submissions seeded: {len(submissions_data)} (1 On-Time, 1 Late)")

    return {
        "users": users_data,
        "courses": courses_data,
        "assignments": assignments_data,
        "submissions": submissions_data,
    }


def init_db():
    """CLI Entrypoint for seeding Firestore."""
    seed_firestore_data()


if __name__ == "__main__":
    init_db()
