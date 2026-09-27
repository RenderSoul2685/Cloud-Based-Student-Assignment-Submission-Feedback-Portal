"""
Authentication and Role-Based Authorization Middleware for FastAPI.
Validates Firebase Bearer tokens and checks Firestore user roles.
"""
from typing import Any, Callable, Dict, List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from cloud.auth_service import verify_firebase_token
from cloud.database_service import DatabaseService

# HTTPBearer with auto_error=False allows custom handling and 401 exceptions
security = HTTPBearer(auto_error=False)


def get_db_service() -> DatabaseService:
    """Dependency provider for DatabaseService."""
    return DatabaseService()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: DatabaseService = Depends(get_db_service),
) -> Dict[str, Any]:
    """
    FastAPI dependency to authenticate requests using Firebase ID tokens.
    
    1. Extracts Bearer token from Authorization header.
    2. Verifies token via Firebase Admin Auth.
    3. Fetches user document from Firestore (/users/{uid}).
    
    Raises:
        HTTPException (401): If token is missing, invalid, expired, or malformed.
        HTTPException (404): If authenticated user has no corresponding Firestore record.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or invalid format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        decoded_token = verify_firebase_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid = decoded_token.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user ID (uid).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get_user(uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with UID '{uid}' not found in database.",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[..., Dict[str, Any]]:
    """
    FastAPI dependency factory that enforces role-based access control (RBAC).
    
    Wraps get_current_user and checks if the user's role is in allowed_roles.
    
    Raises:
        HTTPException (403): If the user's role is not permitted.
    """
    # Normalize allowed roles to string representations
    normalized_allowed = [
        r.value if hasattr(r, "value") else str(r).upper()
        for r in allowed_roles
    ]

    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if hasattr(user_role, "value"):
            user_role = user_role.value
        user_role_str = str(user_role).upper() if user_role else ""

        if user_role_str not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: User role '{user_role_str}' is not authorized to access this resource.",
            )
        return current_user

    return role_checker
