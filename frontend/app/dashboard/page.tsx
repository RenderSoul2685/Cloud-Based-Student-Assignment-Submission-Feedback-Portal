"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/apiClient";
import AppLayout from "@/components/AppLayout";
import LoadingSpinner from "@/components/LoadingSpinner";
import StatusBadge from "@/components/StatusBadge";

interface UpcomingDeadline {
  assignment_id: string;
  course_id: string;
  course_name: string;
  title: string;
  deadline: string;
  max_marks: number;
}

interface RecentGrade {
  submission_id: string;
  assignment_id: string;
  course_id: string;
  assignment_title: string;
  course_name: string;
  marks: number;
  max_marks: number;
  feedback?: string | null;
  graded_at?: string | null;
}

interface StudentDashboardData {
  total_courses: number;
  total_assignments: number;
  pending_count: number;
  overdue_count: number;
  submitted_count: number;
  late_count: number;
  graded_count: number;
  upcoming_deadlines: UpcomingDeadline[];
  recent_grades: RecentGrade[];
}

interface AssignmentNeedingAttention {
  assignment_id: string;
  course_id: string;
  course_name: string;
  title: string;
  deadline: string;
  ungraded_count: number;
  total_submissions: number;
}

interface RecentSubmission {
  submission_id: string;
  assignment_id: string;
  course_id: string;
  student_id: string;
  student_name: string;
  assignment_title: string;
  course_name: string;
  submission_status: "SUBMITTED" | "LATE" | "GRADED" | "NOT_SUBMITTED";
  submitted_at: string;
}

interface TeacherDashboardData {
  total_courses: number;
  total_assignments: number;
  total_students: number;
  ungraded_count: number;
  assignments_needing_attention: AssignmentNeedingAttention[];
  recent_submissions: RecentSubmission[];
}

export default function DashboardPage() {
  const { user, profile, token } = useAuth();
  const toast = useToast();

  const [studentData, setStudentData] = useState<StudentDashboardData | null>(null);
  const [teacherData, setTeacherData] = useState<TeacherDashboardData | null>(null);
  const [fetching, setFetching] = useState(true);

  // RBAC Dev Tester State
  const [testEndpointLoading, setTestEndpointLoading] = useState(false);
  const [testResult, setTestResult] = useState<{
    endpoint: string;
    status: number;
    data: any;
  } | null>(null);

  const loadDashboard = async () => {
    if (!token || !profile) return;
    setFetching(true);

    const isTeacherOrAdmin = profile.role === "TEACHER" || profile.role === "ADMIN";
    const endpoint = isTeacherOrAdmin ? "/api/dashboard/teacher" : "/api/dashboard/student";

    try {
      const data = await api.get(endpoint, { token });
      if (isTeacherOrAdmin) {
        setTeacherData(data);
      } else {
        setStudentData(data);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load dashboard data.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token && profile) {
      loadDashboard();
    }
  }, [token, profile]);

  const runRoleTest = async (endpoint: "/api/student-only" | "/api/teacher-only") => {
    if (!token) return;
    setTestEndpointLoading(true);
    setTestResult(null);

    try {
      const data = await api.get(endpoint, { token });
      setTestResult({
        endpoint,
        status: 200,
        data,
      });
      toast.success(`Role check passed: ${endpoint}`);
    } catch (err: any) {
      setTestResult({
        endpoint,
        status: err.status || 500,
        data: err.data || { error: err.message },
      });
      if (err.status === 403) {
        toast.warning(`Access Forbidden (403): ${endpoint}`);
      } else {
        toast.error(`Request failed (${err.status}): ${err.message}`);
      }
    } finally {
      setTestEndpointLoading(false);
    }
  };

  const role = profile?.role || "STUDENT";
  const isTeacherOrAdmin = role === "TEACHER" || role === "ADMIN";

  return (
    <AppLayout>
      {/* Welcome Banner */}
      <div className="mb-8 p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800/80 shadow-xl relative overflow-hidden">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 border bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-mono">
              <span>⚡</span> {isTeacherOrAdmin ? "Instructor Workspace" : "Student Dashboard"}
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Welcome back, {profile?.name || "User"}
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
              {isTeacherOrAdmin
                ? "Track assignment evaluations, student submissions, and pending grades across your courses."
                : "Track active deadlines, submission verification statuses, awarded scores, and instructor feedback."}
            </p>
          </div>

          {/* Quick Action Navigation */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <Link
              href={isTeacherOrAdmin ? "/teacher/courses" : "/student/courses"}
              id="dashboard-primary-courses-link"
              className="py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-2"
            >
              <span>📚</span>
              <span>{isTeacherOrAdmin ? "Manage Courses" : "Browse Courses"}</span>
            </Link>
            {!isTeacherOrAdmin && (
              <Link
                href="/student/submissions"
                id="dashboard-my-submissions-link"
                className="py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-xs font-semibold border border-slate-700 transition-all flex items-center gap-2"
              >
                <span>📋</span>
                <span>My Submissions</span>
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Main Analytics Content */}
      {fetching ? (
        <LoadingSpinner message="Aggregating real-time dashboard analytics..." />
      ) : isTeacherOrAdmin && teacherData ? (
        /* TEACHER DASHBOARD */
        <div className="space-y-8">
          {/* Stat Cards Matrix */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block mb-1">
                Courses Taught
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-white font-mono" id="teacher-stat-courses">
                  {teacherData.total_courses}
                </span>
                <span className="text-lg">📚</span>
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block mb-1">
                Active Assignments
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-indigo-400 font-mono" id="teacher-stat-assignments">
                  {teacherData.total_assignments}
                </span>
                <span className="text-lg">📝</span>
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block mb-1">
                Active Students
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-emerald-400 font-mono" id="teacher-stat-students">
                  {teacherData.total_students}
                </span>
                <span className="text-lg">👥</span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1 block">Students with submissions</span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block mb-1">
                Awaiting Evaluation
              </span>
              <div className="flex items-baseline justify-between">
                <span
                  className={`text-2xl font-bold font-mono ${
                    teacherData.ungraded_count > 0 ? "text-amber-400" : "text-slate-400"
                  }`}
                  id="teacher-stat-ungraded"
                >
                  {teacherData.ungraded_count}
                </span>
                <span className="text-lg">⏳</span>
              </div>
              <span className="text-[10px] text-slate-500 mt-1 block">Pending deliverable grading</span>
            </div>
          </div>

          {/* Two-Column Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column: Assignments Needing Attention */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                    <span>🎯</span> Assignments Needing Attention
                  </h2>
                  <span className="text-[10px] font-mono text-slate-400">Top Unchecked</span>
                </div>

                {teacherData.assignments_needing_attention.length === 0 ? (
                  <div className="text-center py-10 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
                    <div className="text-3xl mb-2">🎉</div>
                    <h3 className="text-xs font-bold text-white">All Caught Up!</h3>
                    <p className="text-[11px] text-slate-400 max-w-xs mx-auto mt-0.5">
                      {teacherData.total_courses === 0
                        ? "No courses yet. Create your first course to get started."
                        : "No submissions are currently awaiting grading across your assignments."}
                    </p>
                    {teacherData.total_courses === 0 && (
                      <Link
                        href="/teacher/courses"
                        className="mt-3 inline-block py-1.5 px-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg"
                      >
                        Create Course
                      </Link>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {teacherData.assignments_needing_attention.map((item) => (
                      <div
                        key={item.assignment_id}
                        className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-indigo-500/40 transition-all flex items-center justify-between gap-3"
                      >
                        <div className="min-w-0 flex-1">
                          <h3 className="text-xs font-bold text-white truncate">{item.title}</h3>
                          <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5 mt-0.5">
                            <span className="text-indigo-400 truncate max-w-[140px]">{item.course_name}</span>
                            <span>•</span>
                            <span>Due {new Date(item.deadline).toLocaleDateString()}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 flex-shrink-0">
                          <div className="text-right font-mono">
                            <span
                              className={`text-xs font-bold block ${
                                item.ungraded_count > 0 ? "text-amber-400" : "text-slate-400"
                              }`}
                            >
                              {item.ungraded_count} Ungraded
                            </span>
                            <span className="text-[10px] text-slate-500">
                              {item.total_submissions} total
                            </span>
                          </div>

                          <Link
                            href={`/teacher/assignments/${item.assignment_id}/submissions`}
                            id={`grade-attention-btn-${item.assignment_id}`}
                            className="py-1.5 px-3 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/40 transition-all whitespace-nowrap"
                          >
                            Grade &rarr;
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Recent Submissions Feed */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                    <span>⚡</span> Recent Submissions Feed
                  </h2>
                  <span className="text-[10px] font-mono text-slate-400">Latest Activity</span>
                </div>

                {teacherData.recent_submissions.length === 0 ? (
                  <div className="text-center py-10 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
                    <div className="text-3xl mb-2">📥</div>
                    <h3 className="text-xs font-bold text-white">No Submissions Yet</h3>
                    <p className="text-[11px] text-slate-400 max-w-xs mx-auto mt-0.5">
                      Students have not submitted any deliverables for your active assignments yet.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {teacherData.recent_submissions.map((sub) => (
                      <div
                        key={sub.submission_id}
                        className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex items-center justify-between gap-3"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-white truncate">{sub.student_name}</span>
                            <StatusBadge status={sub.submission_status} size="sm" />
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono truncate mt-0.5">
                            {sub.assignment_title} ({sub.course_name})
                          </div>
                        </div>

                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className="text-[10px] text-slate-500 font-mono">
                            {new Date(sub.submitted_at).toLocaleDateString()}
                          </span>
                          <Link
                            href={`/teacher/assignments/${sub.assignment_id}/submissions`}
                            className="py-1 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all"
                          >
                            View
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : studentData ? (
        /* STUDENT DASHBOARD */
        <div className="space-y-8">
          {/* Stat Cards Matrix */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Courses</span>
              <span className="text-xl font-bold text-white font-mono" id="student-stat-courses">
                {studentData.total_courses}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Assignments</span>
              <span className="text-xl font-bold text-indigo-400 font-mono" id="student-stat-assignments">
                {studentData.total_assignments}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Pending</span>
              <span className="text-xl font-bold text-amber-400 font-mono" id="student-stat-pending">
                {studentData.pending_count}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Overdue</span>
              <span className="text-xl font-bold text-rose-400 font-mono" id="student-stat-overdue">
                {studentData.overdue_count}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">On-Time</span>
              <span className="text-xl font-bold text-emerald-400 font-mono" id="student-stat-submitted">
                {studentData.submitted_count}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Late</span>
              <span className="text-xl font-bold text-amber-300 font-mono" id="student-stat-late">
                {studentData.late_count}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md text-center">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Graded</span>
              <span className="text-xl font-bold text-purple-400 font-mono" id="student-stat-graded">
                {studentData.graded_count}
              </span>
            </div>
          </div>

          {/* Two-Column Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column: Upcoming Deadlines */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                    <span>⏰</span> Upcoming Deadlines (Unsubmitted)
                  </h2>
                  <Link
                    href="/student/courses"
                    className="text-[11px] font-semibold text-indigo-400 hover:text-white"
                  >
                    View All &rarr;
                  </Link>
                </div>

                {studentData.upcoming_deadlines.length === 0 ? (
                  <div className="text-center py-10 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
                    <div className="text-3xl mb-2">🎉</div>
                    <h3 className="text-xs font-bold text-white">No Upcoming Deadlines</h3>
                    <p className="text-[11px] text-slate-400 max-w-xs mx-auto mt-0.5">
                      You&apos;re all caught up! You have submitted deliverables for all available assignments.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {studentData.upcoming_deadlines.map((item) => {
                      const deadlineDate = new Date(item.deadline);
                      const now = new Date();
                      const isPast = deadlineDate <= now;
                      const diffHours = Math.round((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60));

                      return (
                        <div
                          key={item.assignment_id}
                          className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-indigo-500/40 transition-all flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0 flex-1">
                            <h3 className="text-xs font-bold text-white truncate">{item.title}</h3>
                            <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5 mt-0.5">
                              <span className="text-indigo-400 truncate max-w-[140px]">{item.course_name}</span>
                              <span>•</span>
                              <span className={isPast ? "text-rose-400 font-semibold" : "text-slate-300"}>
                                {isPast
                                  ? `Overdue (${deadlineDate.toLocaleDateString()})`
                                  : diffHours <= 24
                                  ? `Due soon (< 24h)`
                                  : `Due: ${deadlineDate.toLocaleDateString()}`}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 flex-shrink-0">
                            <span className="text-xs font-mono font-semibold text-slate-400">
                              {item.max_marks} pts
                            </span>
                            <Link
                              href={`/student/courses/${item.course_id}/assignments`}
                              id={`submit-upcoming-btn-${item.assignment_id}`}
                              className="py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all whitespace-nowrap"
                            >
                              Submit &rarr;
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Recent Grades & Feedback */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                    <span>⭐</span> Recent Grades &amp; Feedback
                  </h2>
                  <Link
                    href="/student/submissions"
                    className="text-[11px] font-semibold text-indigo-400 hover:text-white"
                  >
                    History &rarr;
                  </Link>
                </div>

                {studentData.recent_grades.length === 0 ? (
                  <div className="text-center py-10 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
                    <div className="text-3xl mb-2">📋</div>
                    <h3 className="text-xs font-bold text-white">No Graded Assignments Yet</h3>
                    <p className="text-[11px] text-slate-400 max-w-xs mx-auto mt-0.5">
                      Your submitted deliverables are awaiting instructor evaluation.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {studentData.recent_grades.map((grade) => (
                      <div
                        key={grade.submission_id}
                        className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex flex-col gap-2"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <h3 className="text-xs font-bold text-white truncate">{grade.assignment_title}</h3>
                            <span className="text-[10px] text-indigo-400 font-mono">{grade.course_name}</span>
                          </div>
                          <div className="text-right font-mono flex-shrink-0">
                            <span className="text-sm font-bold text-emerald-400">
                              {grade.marks} / {grade.max_marks} pts
                            </span>
                            {grade.graded_at && (
                              <span className="text-[10px] text-slate-500 block">
                                {new Date(grade.graded_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>

                        {grade.feedback && (
                          <div className="text-[11px] text-slate-300 italic bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
                            &quot;{grade.feedback}&quot;
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Collapsed Dev Tools & RBAC Endpoint Tester */}
      <div className="mt-12">
        <details className="group border border-slate-800 rounded-2xl bg-slate-900/40 p-4 transition-all">
          <summary className="cursor-pointer text-xs font-semibold text-slate-400 group-open:text-indigo-400 flex items-center justify-between select-none">
            <div className="flex items-center gap-2">
              <span>🛠️</span>
              <span>Developer Tools &amp; RBAC Endpoint Verification</span>
            </div>
            <span className="text-slate-600 group-open:rotate-180 transition-transform">▼</span>
          </summary>

          <div className="mt-4 pt-4 border-t border-slate-800/80 grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            <div>
              <h3 className="font-bold text-white mb-2">Current Session Token Claims:</h3>
              <dl className="space-y-1.5 text-[11px] font-mono bg-slate-950 p-3 rounded-xl border border-slate-800">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Name:</dt>
                  <dd className="text-slate-200">{profile?.name || "N/A"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Email:</dt>
                  <dd className="text-slate-200">{user?.email}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Role:</dt>
                  <dd className="text-indigo-400 font-bold">{role}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">UID:</dt>
                  <dd className="text-slate-400 truncate max-w-[160px]">{user?.uid}</dd>
                </div>
              </dl>
            </div>

            <div>
              <h3 className="font-bold text-white mb-2">Test FastAPI RBAC Protected Endpoints:</h3>
              <div className="grid grid-cols-2 gap-2 mb-3">
                <button
                  type="button"
                  id="test-student-endpoint-btn"
                  onClick={() => runRoleTest("/api/student-only")}
                  disabled={testEndpointLoading}
                  className="py-2 px-2.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50"
                >
                  GET /api/student-only
                </button>

                <button
                  type="button"
                  id="test-teacher-endpoint-btn"
                  onClick={() => runRoleTest("/api/teacher-only")}
                  disabled={testEndpointLoading}
                  className="py-2 px-2.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-[11px] font-semibold transition-all disabled:opacity-50"
                >
                  GET /api/teacher-only
                </button>
              </div>

              {testResult && (
                <div
                  className={`p-2.5 rounded-lg border text-[11px] font-mono ${
                    testResult.status === 200
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      : testResult.status === 403
                      ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                      : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold">{testResult.endpoint}</span>
                    <span className="px-1.5 py-0.5 rounded font-bold text-[9px] bg-slate-900">
                      HTTP {testResult.status}
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap text-[10px] overflow-x-auto p-1.5 rounded bg-slate-950/60 max-h-24">
                    {JSON.stringify(testResult.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </details>
      </div>
    </AppLayout>
  );
}
