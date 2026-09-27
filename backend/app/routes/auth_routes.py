"""
Authentication & Role-Based Authorization Route Handlers.
Provides Registration, User Profile (/api/me), and Role-Protected Example Endpoints.
"""
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import auth, exceptions as fb_exceptions

from backend.app.models.models import UserRole
from backend.app.models.schemas import RegisterRequest, UserRead
from backend.app.middleware.auth_middleware import get_current_user, require_role
from cloud.auth_service import create_firebase_user, AuthService
from cloud.database_service import DatabaseService

router = APIRouter(prefix="/api", tags=["Authentication & Access Control"])


def get_db_service() -> DatabaseService:
    return DatabaseService()


def get_auth_service() -> AuthService:
    return AuthService()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student or teacher",
)
def register_user(
    request: RegisterRequest,
    db: DatabaseService = Depends(get_db_service),
    auth_srv: AuthService = Depends(get_auth_service),
):
    """
    Registers a new user in Firebase Authentication and creates their profile document in Firestore.
    
    Rules:
    - Only 'STUDENT' and 'TEACHER' roles are allowed for self-registration.
    - Role 'ADMIN' is strictly rejected.
    """
    role_val = request.role.value if hasattr(request.role, "value") else str(request.role)
    role_upper = role_val.upper()

    if role_upper == UserRole.ADMIN.value or role_upper == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration as ADMIN is not permitted. Only STUDENT or TEACHER roles are allowed.",
        )

    if role_upper not in (UserRole.STUDENT.value, UserRole.TEACHER.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role_val}'. Allowed roles are STUDENT and TEACHER.",
        )

    # 1. Create user in Firebase Authentication
    try:
        user_record = auth_srv.create_user(
            email=request.email,
            password=request.password,
            display_name=request.name,
        )
        uid = user_record.uid
    except fb_exceptions.AlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{request.email}' already exists.",
        )
    except Exception as exc:
        err_msg = str(exc)
        if "EMAIL_EXISTS" in err_msg or "already exists" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with email '{request.email}' already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Firebase Auth user: {err_msg}",
        )

    # 2. Set Custom Role Claim on Firebase Token (Optional but ensures RBAC consistency)
    try:
        auth_srv.set_user_role(uid, role_upper)
    except Exception:
        # Non-fatal if claims fail in mock mode
        pass

    # 3. Create /users/{uid} document in Firestore
    now = datetime.now(timezone.utc)
    user_data = {
        "name": request.name,
        "email": request.email,
        "role": role_upper,
        "created_at": now,
    }

    db.create_user(uid, user_data)

    return UserRead(
        uid=uid,
        name=request.name,
        email=request.email,
        role=UserRole(role_upper),
        created_at=now,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current authenticated user profile",
)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns the authenticated user's profile retrieved from Firestore.
    Requires a valid Firebase Bearer token.
    """
    return UserRead.model_validate(current_user)


@router.get(
    "/teacher-only",
    summary="Test endpoint accessible only to Teachers and Admins",
)
def teacher_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """
    Example protected endpoint restricted to TEACHER and ADMIN roles.
    """
    return {
        "message": "Access granted: You are authorized to access the Teacher Portal.",
        "user": current_user,
    }


@router.get(
    "/student-only",
    summary="Test endpoint accessible only to Students",
)
def student_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_role(UserRole.STUDENT)),
):
    """
    Example protected endpoint restricted to STUDENT role.
    """
    return {
        "message": "Access granted: You are authorized to access the Student Portal.",
        "user": current_user,
    }
