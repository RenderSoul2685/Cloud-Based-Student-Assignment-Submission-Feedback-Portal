"""
Firebase Authentication Service Adapter.
Handles server-side token verification, user retrieval, creation, and claims validation.
"""
from typing import Any, Dict, Optional
from firebase_admin import auth
from backend.app.firebase_config import get_firebase_app


def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """
    Validate a Firebase ID token sent from the frontend and return decoded user info (uid, email, etc.).
    Uses firebase-admin's auth.verify_id_token().
    """
    app = get_firebase_app()
    decoded = auth.verify_id_token(id_token, app=app)
    return decoded


def create_firebase_user(email: str, password: str, display_name: Optional[str] = None) -> Any:
    """
    Create a new user in Firebase Auth.
    """
    app = get_firebase_app()
    user_record = auth.create_user(
        email=email,
        password=password,
        display_name=display_name,
        app=app,
    )
    return user_record


class AuthService:
    """
    Firebase Auth Service wrapper.
    Verifies client JWT ID tokens and manages user custom claims.
    """

    def __init__(self):
        self.app = get_firebase_app()

    def verify_token(self, id_token: str) -> Dict[str, Any]:
        """Verify Firebase client JWT ID token and return decoded payload."""
        return verify_firebase_token(id_token)

    def verify_firebase_token(self, id_token: str) -> Dict[str, Any]:
        """Verify Firebase ID token."""
        return verify_firebase_token(id_token)

    def create_user(self, email: str, password: str, display_name: Optional[str] = None) -> Any:
        """Create user in Firebase Auth."""
        return create_firebase_user(email=email, password=password, display_name=display_name)

    def get_user(self, uid: str) -> Any:
        """Retrieve user record from Firebase Auth."""
        return auth.get_user(uid, app=self.app)

    def set_user_role(self, uid: str, role: str) -> None:
        """Set custom role claim (STUDENT, TEACHER, ADMIN) on Firebase user token."""
        auth.set_custom_user_claims(uid, {"role": role}, app=self.app)
