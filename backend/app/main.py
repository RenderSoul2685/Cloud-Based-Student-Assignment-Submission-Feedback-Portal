"""
Main FastAPI Application Entrypoint.
Configures CORS, Rate Limiting (SlowAPI), Routers, and Health Checks.
"""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.app.limiter import limiter
from backend.app.routes.auth_routes import router as auth_router
from backend.app.routes.course_routes import router as course_router
from backend.app.routes.assignment_routes import router as assignment_router
from backend.app.routes.submission_routes import router as submission_router
from backend.app.routes.dashboard_routes import router as dashboard_router

# Configure root logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("assignment_portal")

app = FastAPI(
    title="Cloud-Based Student Assignment Submission & Feedback Portal API",
    description="Backend API supporting Assignment Submission, Evaluation, and Feedback workflow",
    version="1.0.0",
)

# Register SlowAPI Limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ------------------------------------------------------------------------------
# CORS Configuration: Restrict origins based on ALLOWED_ORIGINS env variable
# Defaults to localhost dev URLs if not specified.
# ------------------------------------------------------------------------------
raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
)

if raw_origins.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]

logger.info(f"Configuring CORS with allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(course_router)
app.include_router(assignment_router)
app.include_router(submission_router)
app.include_router(dashboard_router)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Basic health-check endpoint."""
    return {
        "status": "healthy",
        "service": "Cloud Assignment Submission Portal Backend",
        "version": "1.0.0",
        "cloud_providers_supported": ["Google Cloud", "Firebase", "Local Emulator"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
