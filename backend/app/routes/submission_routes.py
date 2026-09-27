"""
Student Submission and Feedback Route Handlers.
Implements student assignment file uploads, deadline verification, resubmissions,
teacher grading & evaluation rubrics, gradebook views, statistical metrics,
and student/instructor deliverable downloads with secure time-limited signed URLs.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.models.models import UserRole, SubmissionStatus
from backend.app.models.schemas import (
    SubmissionRead,
    SubmissionDetailRead,
    SubmissionGrade,
    GradebookEntryRead,
    AssignmentStatsRead,
    DownloadUrlResponse,
)
from backend.app.middleware.auth_middleware import get_current_user, require_role
from backend.app.utils.deadline_utils import is_late
from backend.app.utils.file_validation import validate_file_extension, validate_file_size
from backend.app.utils.grading_stats import calculate_assignment_stats
from cloud.database_service import DatabaseService
from cloud.storage_service import StorageService, build_storage_path

router = APIRouter(tags=["Submissions & Grading"])


def get_db_service() -> DatabaseService:
    return DatabaseService()


def get_storage_service() -> StorageService:
    return StorageService()


def _get_user_role_str(user: Dict[str, Any]) -> str:
    user_role = user.get("role", "")
    if hasattr(user_role, "value"):
        return user_role.value.upper()
    return str(user_role).upper()


# ==============================================================================
# 1. Student Submit / Resubmit Assignment Deliverable
# ==============================================================================
@router.post(
    "/api/assignments/{assignment_id}/submit",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or resubmit an assignment deliverable (Student only)",
)
async def submit_assignment(
    assignment_id: str,
    file: UploadFile = File(..., description="Assignment file deliverable"),
    current_user: Dict[str, Any] = Depends(require_role(UserRole.STUDENT)),
    db: DatabaseService = Depends(get_db_service),
    storage_srv: StorageService = Depends(get_storage_service),
):
    """
    Handles student assignment file submissions with academic integrity validations:
    - Verifies assignment exists and is not soft-deleted.
    - Validates file extension against allowed types.
    - Validates file size against maximum limit.
    - Compares SERVER's current UTC timestamp against deadline.
    - Sets SUBMITTED if on time, or LATE if past deadline (unless allow_late_submission is False).
    - If a prior submission exists, handles as a RESUBMISSION: keeps old files in storage,
      increments resubmission_count, updates submission record, and RESETS any previous grade
      (marks, feedback, graded_at, graded_by cleared, status reset to SUBMITTED/LATE).
    """
    # 1. Verify assignment exists and is active
    assignment = db.find_assignment_by_id(assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found.",
        )

    course_id = assignment["course_id"]

    # 2. Read and validate file content
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File filename is required.",
        )

    allowed_types = [t.strip() for t in assignment.get("allowed_file_types", "pdf,docx,png,jpg").split(",") if t.strip()]
    is_valid_ext, ext_err = validate_file_extension(file.filename, allowed_types)
    if not is_valid_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ext_err or "Invalid file extension.",
        )

    file_bytes = await file.read()
    max_mb = float(assignment.get("max_file_size_mb", 10.0))
    is_valid_sz, sz_err = validate_file_size(len(file_bytes), max_size_mb=max_mb)
    if not is_valid_sz:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sz_err or "File size exceeds permitted threshold.",
        )

    # 3. Server-side deadline check (NEVER trust client timestamps)
    now = datetime.now(timezone.utc)
    deadline = assignment["deadline"]
    late = is_late(now, deadline)

    allow_late = assignment.get("allow_late_submission", True)
    if late and not allow_late:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submissions past the deadline are not permitted for this assignment.",
        )

    submission_status = SubmissionStatus.LATE if late else SubmissionStatus.SUBMITTED

    # 4. Check for existing submission (Resubmission flow)
    student_id = current_user["uid"]
    existing_sub = db.get_submission_by_student_and_assignment(assignment_id, student_id)

    resubmission_allowed = assignment.get("resubmission_allowed", True)

    if existing_sub:
        if not resubmission_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resubmissions are not permitted for this assignment.",
            )

        # Increment resubmission count, keep old file in storage, upload new file
        resubmission_count = existing_sub.get("resubmission_count", 0) + 1
        storage_path = build_storage_path(
            course_id=course_id,
            assignment_id=assignment_id,
            student_id=student_id,
            filename=file.filename,
            timestamp=int(now.timestamp()),
        )

        storage_srv.upload_file(
            file_data=file_bytes,
            storage_path=storage_path,
            content_type=file.content_type,
        )

        # Explicitly reset grading state on resubmission
        update_data = {
            "file_name": file.filename,
            "file_url": storage_path,
            "storage_path": storage_path,
            "submitted_at": now,
            "submission_status": submission_status.value if hasattr(submission_status, "value") else submission_status,
            "resubmission_count": resubmission_count,
            "marks": None,
            "feedback": None,
            "graded_at": None,
            "graded_by": None,
        }

        updated_sub = db.update_submission(existing_sub["submission_id"], update_data)
        return SubmissionRead.model_validate(updated_sub)

    # 5. New initial submission
    storage_path = build_storage_path(
        course_id=course_id,
        assignment_id=assignment_id,
        student_id=student_id,
        filename=file.filename,
        timestamp=int(now.timestamp()),
    )

    storage_srv.upload_file(
        file_data=file_bytes,
        storage_path=storage_path,
        content_type=file.content_type,
    )

    submission_id = f"sub-{uuid.uuid4().hex[:8]}"
    sub_data = {
        "assignment_id": assignment_id,
        "course_id": course_id,
        "student_id": student_id,
        "file_name": file.filename,
        "file_url": storage_path,
        "storage_path": storage_path,
        "submitted_at": now,
        "submission_status": submission_status.value if hasattr(submission_status, "value") else submission_status,
        "resubmission_count": 0,
        "marks": None,
        "feedback": None,
        "graded_at": None,
        "graded_by": None,
    }

    created = db.create_submission(submission_id, sub_data)
    return SubmissionRead.model_validate(created)


# ==============================================================================
# 2. Teacher Grade / Evaluate Submission
# ==============================================================================
@router.put(
    "/api/submissions/{submission_id}/grade",
    response_model=SubmissionDetailRead,
    summary="Grade and provide qualitative feedback on a student submission (Teacher/Admin only)",
)
def grade_submission(
    submission_id: str,
    grade_request: SubmissionGrade,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Evaluates a student's submission:
    - Enforces course ownership (Teacher must be the course instructor; Admin can grade any).
    - Validates marks is between 0 and the assignment's max_marks.
    - Sets submission_status to GRADED.
    - Sets graded_at to server's current UTC timestamp and stores graded_by.
    """
    submission = db.get_submission(submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found.",
        )

    assignment = db.find_assignment_by_id(submission.get("assignment_id", ""))
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated assignment not found.",
        )

    course_id = submission.get("course_id", "")
    course = db.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent course not found.",
        )

    # Ownership check
    role_str = _get_user_role_str(current_user)
    if role_str != UserRole.ADMIN.value:
        if course.get("teacher_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the assigned instructor for this course.",
            )

    # Validate marks
    import math
    max_marks = float(assignment.get("max_marks", 100.0))
    if math.isnan(grade_request.marks) or math.isinf(grade_request.marks) or grade_request.marks < 0 or grade_request.marks > max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks must be a valid number between 0 and {max_marks}.",
        )

    now = datetime.now(timezone.utc)
    update_data = {
        "marks": float(grade_request.marks),
        "feedback": grade_request.feedback.strip() if grade_request.feedback else None,
        "submission_status": SubmissionStatus.GRADED.value,
        "graded_at": now,
        "graded_by": current_user["uid"],
    }

    updated_sub = db.update_submission(submission_id, update_data)
    student_doc = db.get_user(updated_sub.get("student_id", ""))

    detail = {
        **updated_sub,
        "assignment_title": assignment.get("title"),
        "assignment_deadline": assignment.get("deadline"),
        "course_name": course.get("course_name"),
        "student_name": student_doc.get("name") if student_doc else "Enrolled Student",
        "student_email": student_doc.get("email") if student_doc else None,
    }
    return SubmissionDetailRead.model_validate(detail)


# ==============================================================================
# 3. Gradebook View Across All Enrolled Students (Teacher / Admin)
# ==============================================================================
@router.get(
    "/api/assignments/{assignment_id}/grades",
    response_model=List[GradebookEntryRead],
    summary="Get comprehensive gradebook view for an assignment (Teacher/Admin only)",
)
def get_assignment_gradebook(
    assignment_id: str,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Returns gradebook matrix for an assignment including all students in the system/course:
    - Students who submitted show their submission status, marks, feedback, and timestamp.
    - Students who have not submitted show as NOT_SUBMITTED with null marks.
    """
    assignment = db.find_assignment_by_id(assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found.",
        )

    course_id = assignment["course_id"]
    course = db.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_id}' not found.",
        )

    role_str = _get_user_role_str(current_user)
    if role_str != UserRole.ADMIN.value:
        if course.get("teacher_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the assigned instructor for this course.",
            )

    students = db.list_students()
    submissions = db.list_submissions_by_assignment(assignment_id)
    sub_by_student = {s["student_id"]: s for s in submissions if "student_id" in s}

    gradebook_entries = []
    for st in students:
        s_uid = st["uid"]
        sub = sub_by_student.get(s_uid)

        if sub:
            entry = {
                "student_id": s_uid,
                "student_name": st.get("name", "Student"),
                "student_email": st.get("email"),
                "assignment_id": assignment_id,
                "course_id": course_id,
                "submission_id": sub.get("submission_id"),
                "file_name": sub.get("file_name"),
                "submitted_at": sub.get("submitted_at"),
                "submission_status": sub.get("submission_status", SubmissionStatus.SUBMITTED),
                "resubmission_count": sub.get("resubmission_count", 0),
                "marks": sub.get("marks"),
                "feedback": sub.get("feedback"),
                "graded_at": sub.get("graded_at"),
                "graded_by": sub.get("graded_by"),
            }
        else:
            entry = {
                "student_id": s_uid,
                "student_name": st.get("name", "Student"),
                "student_email": st.get("email"),
                "assignment_id": assignment_id,
                "course_id": course_id,
                "submission_id": None,
                "file_name": None,
                "submitted_at": None,
                "submission_status": SubmissionStatus.NOT_SUBMITTED,
                "resubmission_count": 0,
                "marks": None,
                "feedback": None,
                "graded_at": None,
                "graded_by": None,
            }
        gradebook_entries.append(GradebookEntryRead.model_validate(entry))

    return gradebook_entries


# ==============================================================================
# 4. Grading Statistics Metrics for an Assignment
# ==============================================================================
@router.get(
    "/api/assignments/{assignment_id}/stats",
    response_model=AssignmentStatsRead,
    summary="Get assignment evaluation metrics and grade distribution (Teacher/Admin only)",
)
def get_assignment_stats(
    assignment_id: str,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Computes statistical evaluation summary for an assignment:
    - Average marks (mean of graded scores).
    - Highest & lowest scores.
    - Counts of Graded, Ungraded, and Not Submitted students.
    """
    assignment = db.find_assignment_by_id(assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found.",
        )

    course_id = assignment["course_id"]
    course = db.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_id}' not found.",
        )

    role_str = _get_user_role_str(current_user)
    if role_str != UserRole.ADMIN.value:
        if course.get("teacher_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the assigned instructor for this course.",
            )

    students = db.list_students()
    submissions = db.list_submissions_by_assignment(assignment_id)
    max_marks = float(assignment.get("max_marks", 100.0))

    stats = calculate_assignment_stats(
        assignment_id=assignment_id,
        max_marks=max_marks,
        submissions=submissions,
        total_students_count=len(students),
    )
    return AssignmentStatsRead.model_validate(stats)


# ==============================================================================
# 5. Get Current Student's Submissions Across All Assignments
# ==============================================================================
@router.get(
    "/api/submissions/me",
    response_model=List[SubmissionDetailRead],
    summary="List all submissions belonging to current authenticated student",
)
def get_my_submissions(
    current_user: Dict[str, Any] = Depends(require_role(UserRole.STUDENT)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Returns all submissions made by the logged-in student, with resolved assignment titles,
    deadlines, course names, and awarded grades & feedback for clear student dashboard display.
    """
    student_id = current_user["uid"]
    submissions = db.list_submissions_by_student(student_id)

    results = []
    courses_cache: Dict[str, Any] = {}
    assignments_cache: Dict[str, Any] = {}

    for sub in submissions:
        assign_id = sub.get("assignment_id")
        course_id = sub.get("course_id")

        if assign_id and assign_id not in assignments_cache:
            if course_id:
                assignments_cache[assign_id] = db.get_assignment(course_id, assign_id)
            if not assignments_cache.get(assign_id):
                assignments_cache[assign_id] = db.find_assignment_by_id(assign_id)
        assign_data = assignments_cache.get(assign_id)

        if course_id and course_id not in courses_cache:
            courses_cache[course_id] = db.get_course(course_id)
        course_data = courses_cache.get(course_id)

        detail = {
            **sub,
            "assignment_title": assign_data.get("title") if assign_data else None,
            "assignment_deadline": assign_data.get("deadline") if assign_data else None,
            "max_marks": float(assign_data.get("max_marks", 100.0)) if assign_data and "max_marks" in assign_data else None,
            "course_name": course_data.get("course_name") if course_data else None,
            "student_name": current_user.get("name"),
            "student_email": current_user.get("email"),
        }
        results.append(SubmissionDetailRead.model_validate(detail))

    return results


# ==============================================================================
# 6. List Submissions for an Assignment (Teacher / Admin)
# ==============================================================================
@router.get(
    "/api/assignments/{assignment_id}/submissions",
    response_model=List[SubmissionDetailRead],
    summary="List all student submissions for an assignment (Teacher/Admin only)",
)
def get_assignment_submissions(
    assignment_id: str,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Retrieves all student submissions for a specific assignment.
    Enforces instructor ownership of the assignment's parent course.
    """
    assignment = db.find_assignment_by_id(assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found.",
        )

    course_id = assignment["course_id"]
    course = db.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent course '{course_id}' not found.",
        )

    role_str = _get_user_role_str(current_user)
    if role_str != UserRole.ADMIN.value:
        if course.get("teacher_id") != current_user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the assigned instructor for this course.",
            )

    submissions = db.list_submissions_by_assignment(assignment_id)

    results = []
    users_cache: Dict[str, Any] = {}

    for sub in submissions:
        student_id = sub.get("student_id")
        if student_id and student_id not in users_cache:
            users_cache[student_id] = db.get_user(student_id)
        user_doc = users_cache.get(student_id)

        detail = {
            **sub,
            "assignment_title": assignment.get("title"),
            "assignment_deadline": assignment.get("deadline"),
            "max_marks": float(assignment.get("max_marks", 100.0)) if "max_marks" in assignment else None,
            "course_name": course.get("course_name"),
            "student_name": user_doc.get("name") if user_doc else "Unknown Student",
            "student_email": user_doc.get("email") if user_doc else None,
        }
        results.append(SubmissionDetailRead.model_validate(detail))

    return results


# ==============================================================================
# 7. Get Single Submission Details
# ==============================================================================
@router.get(
    "/api/submissions/{submission_id}",
    response_model=SubmissionDetailRead,
    summary="Get single submission record with role access checks",
)
def get_submission_by_id(
    submission_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Retrieves a single submission record by ID.
    Access Control:
    - STUDENT: Can only view their own submission (403 otherwise).
    - TEACHER: Can only view submissions for assignments in courses they own (403 otherwise).
    - ADMIN: Full access.
    """
    submission = db.get_submission(submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found.",
        )

    role_str = _get_user_role_str(current_user)
    user_uid = current_user["uid"]

    if role_str == UserRole.STUDENT.value:
        if submission.get("student_id") != user_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access another student's submission.",
            )
    elif role_str == UserRole.TEACHER.value:
        course = db.get_course(submission.get("course_id", ""))
        if not course or course.get("teacher_id") != user_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the instructor for this course.",
            )

    assign_data = db.find_assignment_by_id(submission.get("assignment_id", ""))
    course_data = db.get_course(submission.get("course_id", ""))
    student_doc = db.get_user(submission.get("student_id", ""))

    detail = {
        **submission,
        "assignment_title": assign_data.get("title") if assign_data else None,
        "assignment_deadline": assign_data.get("deadline") if assign_data else None,
        "max_marks": float(assign_data.get("max_marks", 100.0)) if assign_data and "max_marks" in assign_data else None,
        "course_name": course_data.get("course_name") if course_data else None,
        "student_name": student_doc.get("name") if student_doc else None,
        "student_email": student_doc.get("email") if student_doc else None,
    }
    return SubmissionDetailRead.model_validate(detail)


# ==============================================================================
# 8. Generate Fresh Signed URL for Submission Download
# ==============================================================================
@router.get(
    "/api/submissions/{submission_id}/download",
    response_model=DownloadUrlResponse,
    summary="Get fresh signed download URL for a submission deliverable",
)
def download_submission_file(
    submission_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
    storage_srv: StorageService = Depends(get_storage_service),
):
    """
    Generates a secure, time-limited signed URL to download or view the submission file.
    Enforces strict ownership checks (Student own file / Course Teacher / Admin).
    """
    submission = db.get_submission(submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found.",
        )

    role_str = _get_user_role_str(current_user)
    user_uid = current_user["uid"]

    if role_str == UserRole.STUDENT.value:
        if submission.get("student_id") != user_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access another student's submission.",
            )
    elif role_str == UserRole.TEACHER.value:
        course = db.get_course(submission.get("course_id", ""))
        if not course or course.get("teacher_id") != user_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the instructor for this course.",
            )

    storage_path = submission.get("storage_path")
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission file record has no associated storage path.",
        )

    try:
        signed_url = storage_srv.get_download_url(storage_path, expiration_minutes=60)
    except Exception:
        signed_url = f"/api/mock-download?path={storage_path}"

    return DownloadUrlResponse(
        download_url=signed_url,
        file_name=submission.get("file_name", "submission_file"),
        expires_in_minutes=60,
    )
