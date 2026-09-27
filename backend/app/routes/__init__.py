# Routes Package Exports
from backend.app.routes.auth_routes import router as auth_router
from backend.app.routes.course_routes import router as course_router
from backend.app.routes.assignment_routes import router as assignment_router

__all__ = ["auth_router", "course_router", "assignment_router"]
