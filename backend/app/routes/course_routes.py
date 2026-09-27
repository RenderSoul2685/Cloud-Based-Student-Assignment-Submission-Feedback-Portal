"""
Course Management Route Handlers.
Provides course creation, listing, teacher/student-scoped course views,
and cascading course soft-deletion when submissions exist.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.models import UserRole
from backend.app.models.schemas import CourseCreateRequest, CourseRead
from backend.app.middleware.auth_middleware import get_current_user, require_role
from cloud.database_service import DatabaseService

router = APIRouter(prefix="/api/courses", tags=["Courses"])


def get_db_service() -> DatabaseService:
    return DatabaseService()


@router.post(
    "",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course (Teacher/Admin only)",
)
def create_course(
    request: CourseCreateRequest,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Creates a new course in Firestore (/courses/{courseId}).
    The authenticated teacher's UID is automatically recorded as teacher_id.
    """
    cleaned_name = request.course_name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course name cannot be empty or whitespace only.",
        )

    course_id = f"course-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    course_data = {
        "course_name": cleaned_name,
        "description": (request.description or "").strip(),
        "teacher_id": current_user["uid"],
        "created_at": now,
        "is_deleted": False,
        "deleted_at": None,
    }

    db.create_course(course_id, course_data)

    return CourseRead(
        course_id=course_id,
        course_name=course_data["course_name"],
        description=course_data["description"],
        teacher_id=course_data["teacher_id"],
        created_at=now,
        is_deleted=False,
        deleted_at=None,
    )


@router.get(
    "",
    response_model=List[CourseRead],
    summary="List all available active courses",
)
def list_courses(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Returns all active (non-deleted) courses registered in the system.
    Accessible to all authenticated users.
    """
    courses = db.list_courses()
    active_courses = [c for c in courses if not c.get("is_deleted")]
    return [CourseRead.model_validate(c) for c in active_courses]


@router.get(
    "/mine",
    response_model=List[CourseRead],
    summary="List user's relevant courses",
)
def list_my_courses(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Returns active courses relevant to the authenticated user:
    - Teachers: active courses where teacher_id == current user UID (or all active courses for Admins).
    - Students: all active courses (open enrollment baseline model).
    """
    user_role = str(current_user.get("role", "")).upper()
    if hasattr(current_user.get("role"), "value"):
        user_role = current_user["role"].value.upper()

    if user_role == UserRole.TEACHER.value:
        courses = db.list_courses_by_teacher(current_user["uid"])
    elif user_role == UserRole.ADMIN.value:
        courses = db.list_courses()
    else:
        # Student: Returns all active courses (open enrollment baseline)
        courses = db.list_courses()

    active_courses = [c for c in courses if not c.get("is_deleted")]
    return [CourseRead.model_validate(c) for c in active_courses]


@router.get(
    "/{course_id}",
    response_model=CourseRead,
    summary="Get single course by ID",
)
def get_course(
    course_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Retrieves a single active course document by ID.
    """
    course = db.get_course(course_id)
    if not course or course.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found.",
        )
    return CourseRead.model_validate(course)


@router.delete(
    "/{course_id}",
    summary="Delete or soft-delete a course with cascade support (Teacher/Admin only)",
)
def delete_course(
    course_id: str,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Deletes a course.
    
    Academic Integrity / Cascading Soft-Delete:
    - If ANY assignment under this course has existing student submissions in /submissions:
      * The course is NOT hard-deleted; it is marked soft-deleted (is_deleted: True, deleted_at: now).
      * All assignments under the course are cascade soft-deleted (is_deleted: True, deleted_at: now).
      * Preserves all student submission files, grades, and historical transcripts.
    - If NO assignments have submissions:
      * Hard-deletes all empty assignments in the subcollection.
      * Hard-deletes the course document.
    """
    course = db.get_course(course_id)
    if not course or course.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found.",
        )

    user_role = str(current_user.get("role", "")).upper()
    if hasattr(current_user.get("role"), "value"):
        user_role = current_user["role"].value.upper()

    if user_role != UserRole.ADMIN.value:
        if course.get("teacher_id") != current_user.get("uid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not the assigned instructor for this course.",
            )

    assignments = db.list_assignments(course_id, include_deleted=True)
    has_any_submissions = any(
        db.has_submissions_for_assignment(course_id, a["assignment_id"])
        for a in assignments
    )

    now = datetime.now(timezone.utc)

    if has_any_submissions:
        # Soft-delete course
        db.update_course(
            course_id,
            {
                "is_deleted": True,
                "deleted_at": now,
            },
        )
        # Cascade soft-delete all assignments
        for a in assignments:
            db.update_assignment(
                course_id,
                a["assignment_id"],
                {
                    "is_deleted": True,
                    "deleted_at": now,
                },
            )
        return {
            "message": "Course has existing student submissions and was soft-deleted to preserve academic submission records.",
            "soft_deleted": True,
            "course_id": course_id,
            "assignments_affected": len(assignments),
        }
    else:
        # Hard-delete all assignments
        for a in assignments:
            db.delete_assignment(course_id, a["assignment_id"])
        # Hard-delete course
        db.delete_course(course_id)
        return {
            "message": "Course deleted successfully.",
            "soft_deleted": False,
            "course_id": course_id,
            "assignments_affected": len(assignments),
        }
