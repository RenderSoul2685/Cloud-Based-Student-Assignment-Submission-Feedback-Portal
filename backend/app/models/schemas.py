"""
Pydantic Schemas for Firestore Documents.
Separates Create, Update, and Read representations for API boundary validation.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from backend.app.models.models import UserRole, SubmissionStatus


# ==============================================================================
# User Schemas (/users/{uid})
# ==============================================================================
class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="Unique email address")
    role: UserRole = Field(default=UserRole.STUDENT, description="System role")


class UserCreate(UserBase):
    pass


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")
    role: UserRole = Field(..., description="User role (STUDENT or TEACHER)")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[UserRole] = None


class UserRead(UserBase):
    uid: str = Field(..., description="Firebase Authentication UID / Document ID")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Course Schemas (/courses/{courseId})
# ==============================================================================
class CourseBase(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=255, description="Course title")
    description: Optional[str] = Field(default="", description="Course description")
    teacher_id: str = Field(..., description="Instructor's Firebase UID")


class CourseCreate(CourseBase):
    pass


class CourseCreateRequest(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=255, description="Course title")
    description: Optional[str] = Field(default="", description="Course description")


class CourseUpdate(BaseModel):
    course_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    teacher_id: Optional[str] = None


class CourseRead(CourseBase):
    course_id: str = Field(..., description="Course Firestore Document ID")
    created_at: datetime
    is_deleted: bool = Field(default=False, description="Soft-delete flag")
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Assignment Schemas (/courses/{courseId}/assignments/{assignmentId})
# ==============================================================================
class AssignmentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Assignment title")
    description: str = Field(..., description="Assignment instructions & criteria")
    deadline: datetime = Field(..., description="Timezone-aware deadline timestamp")
    max_marks: float = Field(default=100.0, gt=0.0, allow_inf_nan=False, description="Max attainable score (must be > 0)")
    allowed_file_types: str = Field(default="pdf,docx,png,jpg", description="Allowed extensions")
    max_file_size_mb: float = Field(default=10.0, gt=0.0, allow_inf_nan=False, description="Max file size in MB (must be > 0)")
    allow_late_submission: bool = Field(default=True, description="Whether late submissions are permitted")
    resubmission_allowed: bool = Field(default=True, description="Whether student resubmission is allowed")


class AssignmentCreate(AssignmentBase):
    created_by: str = Field(..., description="Teacher UID who created the assignment")


class AssignmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Assignment title")
    description: str = Field(..., description="Assignment instructions & criteria")
    deadline: datetime = Field(..., description="Timezone-aware deadline timestamp")
    max_marks: float = Field(default=100.0, gt=0.0, allow_inf_nan=False, description="Max attainable score (must be > 0)")
    allowed_file_types: str = Field(default="pdf,docx,png,jpg", description="Allowed extensions")
    max_file_size_mb: float = Field(default=10.0, gt=0.0, allow_inf_nan=False, description="Max file size in MB (must be > 0)")
    allow_late_submission: bool = Field(default=True, description="Whether late submissions are permitted")
    resubmission_allowed: bool = Field(default=True, description="Whether student resubmission is allowed")


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    max_marks: Optional[float] = Field(default=None, gt=0.0, allow_inf_nan=False)
    allowed_file_types: Optional[str] = None
    max_file_size_mb: Optional[float] = Field(default=None, gt=0.0, allow_inf_nan=False)
    allow_late_submission: Optional[bool] = None
    resubmission_allowed: Optional[bool] = None


class AssignmentRead(AssignmentBase):
    assignment_id: str = Field(..., description="Assignment subcollection document ID")
    course_id: str = Field(..., description="Parent course document ID")
    created_by: str
    created_at: datetime
    is_deleted: bool = Field(default=False, description="Soft-delete flag if submissions exist")
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Submission Schemas (/submissions/{submissionId})
# ==============================================================================
class SubmissionBase(BaseModel):
    assignment_id: str = Field(..., description="Associated assignment ID")
    course_id: str = Field(..., description="Parent course ID")
    student_id: str = Field(..., description="Submitting student UID")
    file_name: str = Field(..., description="Original uploaded filename")
    file_url: str = Field(..., description="Storage download URL or storage path")
    storage_path: str = Field(..., description="Firebase Storage blob path")
    resubmission_count: int = Field(default=0, ge=0, description="Number of resubmissions")


class SubmissionCreate(SubmissionBase):
    submission_status: SubmissionStatus = Field(
        default=SubmissionStatus.SUBMITTED,
        description="Submission status",
    )


class SubmissionGrade(BaseModel):
    marks: float = Field(..., ge=0.0, allow_inf_nan=False, description="Awarded marks")
    feedback: Optional[str] = Field(default=None, description="Teacher feedback comments")


class SubmissionRead(SubmissionBase):
    submission_id: str = Field(..., description="Submission document ID")
    submitted_at: datetime
    submission_status: SubmissionStatus
    marks: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None
    graded_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionDetailRead(SubmissionRead):
    assignment_title: Optional[str] = Field(default=None, description="Resolved assignment title")
    assignment_deadline: Optional[datetime] = Field(default=None, description="Resolved assignment deadline")
    max_marks: Optional[float] = Field(default=None, description="Resolved assignment max marks")
    course_name: Optional[str] = Field(default=None, description="Resolved course name")
    student_name: Optional[str] = Field(default=None, description="Resolved student name")
    student_email: Optional[str] = Field(default=None, description="Resolved student email")

    model_config = ConfigDict(from_attributes=True)


class GradebookEntryRead(BaseModel):
    student_id: str = Field(..., description="Student Firebase UID")
    student_name: str = Field(..., description="Full student name")
    student_email: Optional[str] = Field(default=None, description="Student email address")
    assignment_id: str = Field(..., description="Assignment ID")
    course_id: str = Field(..., description="Course ID")
    submission_id: Optional[str] = Field(default=None, description="Submission doc ID if submitted")
    file_name: Optional[str] = Field(default=None, description="Submitted deliverable filename")
    submitted_at: Optional[datetime] = Field(default=None, description="Submission timestamp")
    submission_status: SubmissionStatus = Field(default=SubmissionStatus.NOT_SUBMITTED)
    resubmission_count: int = Field(default=0)
    marks: Optional[float] = Field(default=None, description="Awarded score")
    feedback: Optional[str] = Field(default=None, description="Instructor feedback")
    graded_at: Optional[datetime] = Field(default=None, description="Grading timestamp")
    graded_by: Optional[str] = Field(default=None, description="Teacher UID who evaluated")

    model_config = ConfigDict(from_attributes=True)


class AssignmentStatsRead(BaseModel):
    assignment_id: str = Field(..., description="Assignment ID")
    total_students: int = Field(..., description="Total student count in system / course")
    total_submissions: int = Field(..., description="Total submissions received")
    graded_count: int = Field(..., description="Count of graded submissions")
    ungraded_count: int = Field(..., description="Count of submitted but ungraded submissions")
    not_submitted_count: int = Field(..., description="Count of students with no submission")
    average_marks: Optional[float] = Field(default=None, description="Mean marks of graded submissions")
    highest_marks: Optional[float] = Field(default=None, description="Highest score awarded")
    lowest_marks: Optional[float] = Field(default=None, description="Lowest score awarded")
    max_marks: float = Field(..., description="Assignment max attainable marks")


class DownloadUrlResponse(BaseModel):
    download_url: str = Field(..., description="Time-limited signed download URL")
    file_name: str = Field(..., description="Original file name")
    expires_in_minutes: int = Field(default=60, description="URL expiration duration in minutes")


# ==============================================================================
# Dashboard Aggregation Models
# ==============================================================================
class UpcomingDeadlineRead(BaseModel):
    assignment_id: str = Field(..., description="Assignment ID")
    course_id: str = Field(..., description="Course ID")
    course_name: str = Field(..., description="Course name")
    title: str = Field(..., description="Assignment title")
    deadline: datetime = Field(..., description="Due timestamp")
    max_marks: float = Field(..., description="Max marks")


class RecentGradeRead(BaseModel):
    submission_id: str = Field(..., description="Submission ID")
    assignment_id: str = Field(..., description="Assignment ID")
    course_id: str = Field(..., description="Course ID")
    assignment_title: str = Field(..., description="Assignment title")
    course_name: str = Field(..., description="Course name")
    marks: float = Field(..., description="Awarded marks")
    max_marks: float = Field(..., description="Assignment max marks")
    feedback: Optional[str] = Field(default=None, description="Teacher feedback comments")
    graded_at: Optional[datetime] = Field(default=None, description="Grading timestamp")


class StudentDashboardRead(BaseModel):
    total_courses: int = Field(..., description="Count of visible courses")
    total_assignments: int = Field(..., description="Count of active assignments across courses")
    pending_count: int = Field(..., description="Unsubmitted assignments whose deadline has not passed")
    overdue_count: int = Field(..., description="Unsubmitted assignments whose deadline has passed")
    submitted_count: int = Field(..., description="Student's submissions on-time")
    late_count: int = Field(..., description="Student's submissions late")
    graded_count: int = Field(..., description="Student's submissions graded")
    upcoming_deadlines: List[UpcomingDeadlineRead] = Field(default_factory=list, description="Next unsubmitted deadlines")
    recent_grades: List[RecentGradeRead] = Field(default_factory=list, description="Latest graded deliverables")


class AssignmentNeedingAttentionRead(BaseModel):
    assignment_id: str = Field(..., description="Assignment ID")
    course_id: str = Field(..., description="Course ID")
    course_name: str = Field(..., description="Course name")
    title: str = Field(..., description="Assignment title")
    deadline: datetime = Field(..., description="Assignment deadline")
    ungraded_count: int = Field(..., description="Submissions awaiting grading")
    total_submissions: int = Field(..., description="Total submissions received")


class RecentSubmissionRead(BaseModel):
    submission_id: str = Field(..., description="Submission ID")
    assignment_id: str = Field(..., description="Assignment ID")
    course_id: str = Field(..., description="Course ID")
    student_id: str = Field(..., description="Student UID")
    student_name: str = Field(..., description="Student full name")
    assignment_title: str = Field(..., description="Assignment title")
    course_name: str = Field(..., description="Course name")
    submission_status: SubmissionStatus = Field(..., description="Submission status")
    submitted_at: datetime = Field(..., description="Submission timestamp")


class TeacherDashboardRead(BaseModel):
    total_courses: int = Field(..., description="Count of courses taught")
    total_assignments: int = Field(..., description="Count of active assignments across courses")
    total_students: int = Field(..., description="Distinct students who submitted coursework")
    ungraded_count: int = Field(..., description="Total submissions awaiting evaluation")
    assignments_needing_attention: List[AssignmentNeedingAttentionRead] = Field(
        default_factory=list, description="Top assignments with highest pending evaluation count"
    )
    recent_submissions: List[RecentSubmissionRead] = Field(
        default_factory=list, description="Most recent student submissions"
    )

