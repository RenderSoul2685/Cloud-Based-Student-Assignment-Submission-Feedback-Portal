"""
Role-Specific Dashboard Aggregation Endpoints for Students, Teachers, and Admins.

Performance & Scale Notes:
--------------------------
For this university/student portal scale, aggregation is computed on-the-fly by querying
active courses, subcollection assignments, and student submissions.
At high-throughput enterprise scale (100,000+ submissions), best practices for NoSQL Firestore include:
1. Distributed Firestore counters (e.g. Firebase Extensions or Cloud Functions incrementing
   `ungraded_count` and `total_submissions` per assignment doc).
2. Denormalizing course enrollment lists (`student_ids` array or dedicated `enrollments` collection).
3. Using collection group index queries with pagination for recent submissions (`collectionGroup('submissions')`).
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.schemas import (
    UserRole,
    SubmissionStatus,
    StudentDashboardRead,
    UpcomingDeadlineRead,
    RecentGradeRead,
    TeacherDashboardRead,
    AssignmentNeedingAttentionRead,
    RecentSubmissionRead,
)
from backend.app.middleware.auth_middleware import get_current_user, require_role
from backend.app.utils.deadline_utils import ensure_utc
from cloud.database_service import DatabaseService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def get_db_service() -> DatabaseService:
    return DatabaseService()


def _get_user_role_str(user: Dict[str, Any]) -> str:
    role_val = user.get("role")
    if hasattr(role_val, "value"):
        return str(role_val.value)
    return str(role_val) if role_val else UserRole.STUDENT.value


# ==============================================================================
# 1. Student Dashboard Aggregation
# ==============================================================================
@router.get(
    "/student",
    response_model=StudentDashboardRead,
    summary="Get aggregated metrics and activity feeds for the authenticated student",
)
def get_student_dashboard(
    current_user: Dict[str, Any] = Depends(require_role(UserRole.STUDENT)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Computes real-time overview metrics for the student:
    - total_courses & total_assignments across all accessible courses
    - pending vs overdue counts for unsubmitted assignments (calculated against server UTC time)
    - submitted, late, and graded submission counts
    - top 5 upcoming unsubmitted deadlines (ordered chronologically)
    - top 5 most recently graded submissions with feedback
    """
    student_id = current_user["uid"]
    now_utc = datetime.now(timezone.utc)

    # 1. Fetch all visible courses
    courses = db.list_courses()
    course_map = {c["course_id"]: c.get("course_name", "Course") for c in courses}
    total_courses = len(courses)

    # 2. Fetch all active assignments across all courses
    all_assignments = []
    assignment_map: Dict[str, Dict[str, Any]] = {}

    for c in courses:
        c_id = c["course_id"]
        c_assigns = db.list_assignments(c_id, include_deleted=False)
        for a in c_assigns:
            a_id = a["assignment_id"]
            assign_entry = {
                **a,
                "course_name": course_map.get(c_id, "Course"),
            }
            all_assignments.append(assign_entry)
            assignment_map[a_id] = assign_entry

    total_assignments = len(all_assignments)

    # 3. Fetch student's own submissions
    my_submissions = db.list_submissions_by_student(student_id)
    sub_by_assign: Dict[str, Dict[str, Any]] = {}
    for s in my_submissions:
        a_id = s.get("assignment_id")
        if a_id:
            sub_by_assign[a_id] = s

    # 4. Compute submission counts
    submitted_count = 0
    late_count = 0
    graded_count = 0

    for s in my_submissions:
        st = s.get("submission_status")
        if hasattr(st, "value"):
            st = st.value
        st_str = str(st).upper()

        if st_str == SubmissionStatus.SUBMITTED.value:
            submitted_count += 1
        elif st_str == SubmissionStatus.LATE.value:
            late_count += 1
        elif st_str == SubmissionStatus.GRADED.value:
            graded_count += 1

    # 5. Compute pending vs overdue for unsubmitted assignments
    pending_count = 0
    overdue_count = 0
    unsubmitted_assignments = []

    for a in all_assignments:
        a_id = a["assignment_id"]
        if a_id not in sub_by_assign:
            unsubmitted_assignments.append(a)
            raw_deadline = a.get("deadline")
            deadline_utc = ensure_utc(raw_deadline)

            if deadline_utc > now_utc:
                pending_count += 1
            else:
                overdue_count += 1

    # 6. Upcoming deadlines (top 5 unsubmitted assignments, sorted by deadline ascending)
    def parse_deadline_sort(item: Dict[str, Any]) -> datetime:
        return ensure_utc(item.get("deadline"))

    unsubmitted_assignments.sort(key=parse_deadline_sort)
    upcoming_slice = unsubmitted_assignments[:5]

    upcoming_deadlines = [
        UpcomingDeadlineRead(
            assignment_id=item["assignment_id"],
            course_id=item["course_id"],
            course_name=item.get("course_name", "Course"),
            title=item.get("title", "Assignment"),
            deadline=ensure_utc(item.get("deadline")),
            max_marks=float(item.get("max_marks", 100.0)),
        )
        for item in upcoming_slice
    ]

    # 7. Recent grades (top 5 graded submissions, sorted by graded_at descending)
    graded_submissions = [
        s for s in my_submissions
        if (
            str(getattr(s.get("submission_status"), "value", s.get("submission_status"))).upper() == SubmissionStatus.GRADED.value
            or s.get("marks") is not None
        )
    ]

    def parse_graded_sort(item: Dict[str, Any]) -> datetime:
        raw_g = item.get("graded_at") or item.get("submitted_at")
        return ensure_utc(raw_g)

    graded_submissions.sort(key=parse_graded_sort, reverse=True)
    recent_grades_slice = graded_submissions[:5]

    recent_grades = []
    for s in recent_grades_slice:
        a_id = s.get("assignment_id", "")
        c_id = s.get("course_id", "")
        assign_doc = assignment_map.get(a_id) or db.find_assignment_by_id(a_id) or {}
        course_name = course_map.get(c_id) or assign_doc.get("course_name") or "Course"

        recent_grades.append(
            RecentGradeRead(
                submission_id=s["submission_id"],
                assignment_id=a_id,
                course_id=c_id,
                assignment_title=assign_doc.get("title", a_id),
                course_name=course_name,
                marks=float(s.get("marks", 0.0)),
                max_marks=float(assign_doc.get("max_marks", 100.0)),
                feedback=s.get("feedback"),
                graded_at=ensure_utc(s.get("graded_at")) if s.get("graded_at") else None,
            )
        )

    return StudentDashboardRead(
        total_courses=total_courses,
        total_assignments=total_assignments,
        pending_count=pending_count,
        overdue_count=overdue_count,
        submitted_count=submitted_count,
        late_count=late_count,
        graded_count=graded_count,
        upcoming_deadlines=upcoming_deadlines,
        recent_grades=recent_grades,
    )


# ==============================================================================
# 2. Teacher Dashboard Aggregation
# ==============================================================================
@router.get(
    "/teacher",
    response_model=TeacherDashboardRead,
    summary="Get aggregated metrics and evaluation feeds for the authenticated teacher/admin",
)
def get_teacher_dashboard(
    current_user: Dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: DatabaseService = Depends(get_db_service),
):
    """
    Computes real-time overview metrics for instructors / admins:
    - total_courses: courses taught by instructor (or all courses if ADMIN)
    - total_assignments: active assignments across taught courses
    - total_students: count of distinct students who submitted work across instructor courses
    - ungraded_count: total student deliverables awaiting evaluation
    - assignments_needing_attention: top 5 assignments with the highest ungraded count
    - recent_submissions: top 5 latest submissions across instructor courses
    """
    user_uid = current_user["uid"]
    role_str = _get_user_role_str(current_user)

    # 1. Fetch courses owned by teacher (or all if admin)
    all_courses = db.list_courses()
    if role_str == UserRole.ADMIN.value:
        teacher_courses = all_courses
    else:
        teacher_courses = [c for c in all_courses if c.get("teacher_id") == user_uid]

    total_courses = len(teacher_courses)
    course_map = {c["course_id"]: c.get("course_name", "Course") for c in teacher_courses}

    # 2. Fetch all assignments in teacher courses
    teacher_assignments = []
    assignment_map: Dict[str, Dict[str, Any]] = {}

    for c in teacher_courses:
        c_id = c["course_id"]
        c_assigns = db.list_assignments(c_id, include_deleted=False)
        for a in c_assigns:
            a_id = a["assignment_id"]
            assign_entry = {
                **a,
                "course_name": course_map.get(c_id, "Course"),
            }
            teacher_assignments.append(assign_entry)
            assignment_map[a_id] = assign_entry

    total_assignments = len(teacher_assignments)

    # 3. Gather submissions for all teacher assignments
    all_teacher_submissions = []
    assignment_submission_stats: Dict[str, Dict[str, Any]] = {}
    distinct_student_ids = set()
    total_ungraded_count = 0

    for a in teacher_assignments:
        a_id = a["assignment_id"]
        subs = db.list_submissions_by_assignment(a_id)
        ungraded_in_assign = 0

        for s in subs:
            s_uid = s.get("student_id")
            if s_uid:
                distinct_student_ids.add(s_uid)

            # Check if graded
            st = s.get("submission_status")
            if hasattr(st, "value"):
                st = st.value
            st_str = str(st).upper()

            is_graded = (st_str == SubmissionStatus.GRADED.value and s.get("marks") is not None)
            if not is_graded:
                ungraded_in_assign += 1
                total_ungraded_count += 1

            all_teacher_submissions.append({
                **s,
                "assignment_title": a.get("title", a_id),
                "course_name": a.get("course_name", "Course"),
            })

        assignment_submission_stats[a_id] = {
            "assignment": a,
            "ungraded_count": ungraded_in_assign,
            "total_submissions": len(subs),
        }

    total_students = len(distinct_student_ids)

    # 4. Assignments needing attention (top 5 with highest ungraded_count)
    # Sort primarily by ungraded_count descending, secondarily by total_submissions descending
    sorted_assign_stats = sorted(
        assignment_submission_stats.values(),
        key=lambda item: (item["ungraded_count"], item["total_submissions"]),
        reverse=True,
    )

    # Pick top 5 assignments
    top_attention = sorted_assign_stats[:5]
    assignments_needing_attention = [
        AssignmentNeedingAttentionRead(
            assignment_id=item["assignment"]["assignment_id"],
            course_id=item["assignment"]["course_id"],
            course_name=item["assignment"].get("course_name", "Course"),
            title=item["assignment"].get("title", "Assignment"),
            deadline=ensure_utc(item["assignment"].get("deadline")),
            ungraded_count=item["ungraded_count"],
            total_submissions=item["total_submissions"],
        )
        for item in top_attention
    ]

    # 5. Recent submissions feed (top 5 sorted by submitted_at descending)
    def parse_submitted_sort(item: Dict[str, Any]) -> datetime:
        return ensure_utc(item.get("submitted_at"))

    all_teacher_submissions.sort(key=parse_submitted_sort, reverse=True)
    recent_slice = all_teacher_submissions[:5]

    # Pre-cache student users
    user_cache: Dict[str, Dict[str, Any]] = {}
    recent_submissions = []

    for s in recent_slice:
        s_uid = s.get("student_id", "")
        if s_uid and s_uid not in user_cache:
            user_cache[s_uid] = db.get_user(s_uid) or {}
        student_doc = user_cache.get(s_uid, {})

        st = s.get("submission_status", SubmissionStatus.SUBMITTED)
        if isinstance(st, str):
            st = SubmissionStatus(st)

        recent_submissions.append(
            RecentSubmissionRead(
                submission_id=s.get("submission_id", ""),
                assignment_id=s.get("assignment_id", ""),
                course_id=s.get("course_id", ""),
                student_id=s_uid,
                student_name=student_doc.get("name") or s.get("student_name") or "Student",
                assignment_title=s.get("assignment_title", "Assignment"),
                course_name=s.get("course_name", "Course"),
                submission_status=st,
                submitted_at=ensure_utc(s.get("submitted_at")),
            )
        )

    return TeacherDashboardRead(
        total_courses=total_courses,
        total_assignments=total_assignments,
        total_students=total_students,
        ungraded_count=total_ungraded_count,
        assignments_needing_attention=assignments_needing_attention,
        recent_submissions=recent_submissions,
    )
