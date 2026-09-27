from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routes.auth_routes import router as auth_router
from backend.app.routes.course_routes import router as course_router
from backend.app.routes.assignment_routes import router as assignment_router
from backend.app.routes.submission_routes import router as submission_router
from backend.app.routes.dashboard_routes import router as dashboard_router

app = FastAPI(
    title="Cloud-Based Student Assignment Submission & Feedback Portal API",
    description="Backend API supporting Assignment Submission, Evaluation, and Feedback workflow",
    version="1.0.0",
)

# Enable CORS for local development and frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
