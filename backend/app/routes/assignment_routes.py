"""
Assignment Management Route Handlers.
Implements Course Assignment Subcollection CRUD (/courses/{courseId}/assignments/{assignmentId}).
Enforces teacher course ownership and soft-deletion when submissions exist.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.models import UserRole
from backend.app.models.schemas import (
    AssignmentCreateRequest,
    AssignmentRead,
    AssignmentUpdate,
)
from backend.app.middleware.auth_middleware import get_current_user, require_role
from cloud.database_service import DatabaseService

router = APIRouter(prefix="/api/courses/{course_id}/assignments", tags=["Assignments"])


def get_db_service() -> DatabaseService:
    return DatabaseService()


def _verify_course_ownership(
    course_id: str,
    current_user: Dict[str, Any],
    db: DatabaseService,
) -> Dict[str, Any]:
    """
    Validates that the course exists and the requesting teacher is the course instructor (or Admin).
    """
    course = db.get_course(course_id)
    if not course:
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

    return course


@router.post(
    "",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assignment for a course (Teacher/Admin only)",
)
def create_assignment(
    course_id: str,
    request: AssignmentCreateRequest,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Creates an assignment document in the subcollection /courses/{courseId}/assignments/{assignmentId}.
    
    Validations:
    - Course must exist.
    - Teacher must own the course.
    - Deadline must be in the future.
    - Max marks must be > 0.
    - Max file size must be > 0.
    - Allowed file types must be non-empty.
    """
    _verify_course_ownership(course_id, current_user, db)

    import math

    now = datetime.now(timezone.utc)
    deadline = request.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    if deadline <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment deadline must be a future date and time.",
        )

    if not request.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment title cannot be empty or whitespace only.",
        )

    if not request.description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment description cannot be empty or whitespace only.",
        )

    if math.isnan(request.max_marks) or math.isinf(request.max_marks) or request.max_marks <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum marks must be a valid positive number greater than 0.",
        )

    if math.isnan(request.max_file_size_mb) or math.isinf(request.max_file_size_mb) or request.max_file_size_mb <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum file size in MB must be a valid positive number greater than 0.",
        )

    if not request.allowed_file_types or not request.allowed_file_types.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allowed file types must be specified (e.g. 'pdf,docx,zip').",
        )

    assignment_id = f"assign-{uuid.uuid4().hex[:8]}"
    assignment_data = {
        "title": request.title.strip(),
        "description": request.description.strip(),
        "deadline": deadline,
        "max_marks": float(request.max_marks),
        "allowed_file_types": request.allowed_file_types.strip().lower(),
        "max_file_size_mb": float(request.max_file_size_mb),
        "allow_late_submission": request.allow_late_submission,
        "resubmission_allowed": request.resubmission_allowed,
        "created_by": current_user["uid"],
        "created_at": now,
        "is_deleted": False,
        "deleted_at": None,
    }

    db.create_assignment(course_id, assignment_id, assignment_data)

    return AssignmentRead(
        assignment_id=assignment_id,
        course_id=course_id,
        title=assignment_data["title"],
        description=assignment_data["description"],
        deadline=assignment_data["deadline"],
        max_marks=assignment_data["max_marks"],
        allowed_file_types=assignment_data["allowed_file_types"],
        max_file_size_mb=assignment_data["max_file_size_mb"],
        allow_late_submission=assignment_data["allow_late_submission"],
        resubmission_allowed=assignment_data["resubmission_allowed"],
        created_by=assignment_data["created_by"],
        created_at=assignment_data["created_at"],
        is_deleted=False,
        deleted_at=None,
    )


@router.get(
    "",
    response_model=List[AssignmentRead],
    summary="List all active assignments for a course",
)
def list_assignments(
    course_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Returns all non-deleted assignments under /courses/{courseId}/assignments.
    Accessible to all authenticated students and instructors.
    """
    course = db.get_course(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found.",
        )

    assignments = db.list_assignments(course_id, include_deleted=False)
    return [AssignmentRead.model_validate(a) for a in assignments]


@router.get(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Get assignment details by ID",
)
def get_assignment(
    course_id: str,
    assignment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Retrieves a single assignment by ID.
    """
    assignment = db.get_assignment(course_id, assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in course '{course_id}'.",
        )

    return AssignmentRead.model_validate(assignment)


@router.put(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Update an existing assignment (Teacher/Admin only)",
)
def update_assignment(
    course_id: str,
    assignment_id: str,
    request: AssignmentUpdate,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Updates assignment fields (title, description, deadline, max_marks, allowed_file_types, max_file_size_mb).
    Enforces instructor course ownership.
    """
    _verify_course_ownership(course_id, current_user, db)

    assignment = db.get_assignment(course_id, assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in course '{course_id}'.",
        )

    update_dict = request.model_dump(exclude_unset=True)
    import math

    if "title" in update_dict and update_dict["title"] is not None:
        if not update_dict["title"].strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title cannot be empty or whitespace only.",
            )
        update_dict["title"] = update_dict["title"].strip()

    if "description" in update_dict and update_dict["description"] is not None:
        if not update_dict["description"].strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Description cannot be empty or whitespace only.",
            )
        update_dict["description"] = update_dict["description"].strip()

    if "deadline" in update_dict and update_dict["deadline"] is not None:
        deadline = update_dict["deadline"]
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated deadline must be in the future.",
            )
        update_dict["deadline"] = deadline

    if "max_marks" in update_dict and update_dict["max_marks"] is not None:
        if math.isnan(update_dict["max_marks"]) or math.isinf(update_dict["max_marks"]) or update_dict["max_marks"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum marks must be a valid number greater than 0.",
            )

    if "max_file_size_mb" in update_dict and update_dict["max_file_size_mb"] is not None:
        if math.isnan(update_dict["max_file_size_mb"]) or math.isinf(update_dict["max_file_size_mb"]) or update_dict["max_file_size_mb"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum file size in MB must be a valid number greater than 0.",
            )

    if "allowed_file_types" in update_dict and update_dict["allowed_file_types"] is not None:
        if not update_dict["allowed_file_types"].strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Allowed file types cannot be empty.",
            )
        update_dict["allowed_file_types"] = update_dict["allowed_file_types"].strip().lower()

    if update_dict:
        updated = db.update_assignment(course_id, assignment_id, update_dict)
    else:
        updated = assignment

    return AssignmentRead.model_validate(updated)


@router.delete(
    "/{assignment_id}",
    summary="Delete or soft-delete an assignment (Teacher/Admin only)",
)
def delete_assignment(
    course_id: str,
    assignment_id: str,
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Deletes an assignment.
    
    Academic Integrity / Soft-Delete Strategy:
    - If student submissions already exist for this assignment in /submissions, 
      the assignment is NOT hard-deleted. Instead, it is marked as soft-deleted (is_deleted: true, deleted_at: now).
      This preserves existing submission files, grading history, and student records.
    - If NO submissions exist, the document is safely removed from the subcollection.
    """
    _verify_course_ownership(course_id, current_user, db)

    assignment = db.get_assignment(course_id, assignment_id)
    if not assignment or assignment.get("is_deleted") is True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in course '{course_id}'.",
        )

    # Check if student submissions exist for this assignment
    has_submissions = db.has_submissions_for_assignment(course_id, assignment_id)

    if has_submissions:
        # Soft-delete assignment
        now = datetime.now(timezone.utc)
        db.update_assignment(
            course_id,
            assignment_id,
            {
                "is_deleted": True,
                "deleted_at": now,
            },
        )
        return {
            "message": "Assignment has existing submissions and was soft-deleted to preserve academic submission records.",
            "soft_deleted": True,
            "assignment_id": assignment_id,
            "course_id": course_id,
        }
    else:
        # Hard-delete assignment
        db.delete_assignment(course_id, assignment_id)
        return {
            "message": "Assignment deleted successfully.",
            "soft_deleted": False,
            "assignment_id": assignment_id,
            "course_id": course_id,
        }
