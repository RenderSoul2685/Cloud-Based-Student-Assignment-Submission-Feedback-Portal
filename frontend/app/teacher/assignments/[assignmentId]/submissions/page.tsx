"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import AppLayout from "@/components/AppLayout";
import LoadingSpinner from "@/components/LoadingSpinner";
import StatusBadge from "@/components/StatusBadge";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/apiClient";

interface SubmissionDetail {
  submission_id: string;
  assignment_id: string;
  course_id: string;
  student_id: string;
  file_name: string;
  file_url: string;
  storage_path: string;
  submitted_at: string;
  submission_status: "SUBMITTED" | "LATE" | "GRADED" | "NOT_SUBMITTED";
  resubmission_count: number;
  marks?: number | null;
  feedback?: string | null;
  graded_at?: string | null;
  graded_by?: string | null;
  assignment_title?: string | null;
  assignment_deadline?: string | null;
  course_name?: string | null;
  student_name?: string | null;
  student_email?: string | null;
}

interface GradebookEntry {
  student_id: string;
  student_name: string;
  student_email?: string | null;
  assignment_id: string;
  course_id: string;
  submission_id?: string | null;
  file_name?: string | null;
  submitted_at?: string | null;
  submission_status: "SUBMITTED" | "LATE" | "GRADED" | "NOT_SUBMITTED";
  resubmission_count: number;
  marks?: number | null;
  feedback?: string | null;
  graded_at?: string | null;
  graded_by?: string | null;
}

interface AssignmentStats {
  assignment_id: string;
  total_students: number;
  total_submissions: number;
  graded_count: number;
  ungraded_count: number;
  not_submitted_count: number;
  average_marks?: number | null;
  highest_marks?: number | null;
  lowest_marks?: number | null;
  max_marks: number;
}

export default function TeacherAssignmentSubmissionsPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = use(params);
  const router = useRouter();
  const { user, profile, token, loading } = useAuth();
  const toast = useToast();

  const [submissions, setSubmissions] = useState<SubmissionDetail[]>([]);
  const [gradebook, setGradebook] = useState<GradebookEntry[]>([]);
  const [stats, setStats] = useState<AssignmentStats | null>(null);
  const [activeTab, setActiveTab] = useState<"submissions" | "gradebook">("submissions");
  const [fetching, setFetching] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Grading Modal State
  const [gradingSubmission, setGradingSubmission] = useState<{
    submissionId: string;
    studentName: string;
    fileName: string;
    currentMarks: number | string;
    currentFeedback: string;
    maxMarks: number;
  } | null>(null);
  const [gradeMarks, setGradeMarks] = useState<number | string>("");
  const [gradeFeedback, setGradeFeedback] = useState<string>("");
  const [gradingSubmitting, setGradingSubmitting] = useState(false);
  const [gradingError, setGradingError] = useState<string | null>(null);

  // Route Guard: TEACHER or ADMIN
  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace("/login");
      } else if (profile && profile.role !== "TEACHER" && profile.role !== "ADMIN") {
        router.replace("/dashboard");
      }
    }
  }, [user, profile, loading, router]);

  const loadAllData = async () => {
    if (!token) return;
    setFetching(true);
    try {
      // 1. Fetch Submissions
      const subData = await api.get<SubmissionDetail[]>(
        `/api/assignments/${assignmentId}/submissions`,
        { token }
      );
      subData.sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime());
      setSubmissions(subData);

      // 2. Fetch Gradebook
      try {
        const gbData = await api.get<GradebookEntry[]>(
          `/api/assignments/${assignmentId}/grades`,
          { token }
        );
        setGradebook(gbData);
      } catch {
        // Optional gradebook endpoint fallback
      }

      // 3. Fetch Stats
      try {
        const statsData = await api.get<AssignmentStats>(
          `/api/assignments/${assignmentId}/stats`,
          { token }
        );
        setStats(statsData);
      } catch {
        // Optional stats endpoint fallback
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load submissions.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadAllData();
    }
  }, [token, assignmentId]);

  const handleOpenGradeModal = (
    submissionId: string,
    studentName: string,
    fileName: string,
    marks?: number | null,
    feedback?: string | null
  ) => {
    const maxMarks = stats?.max_marks || 100;
    setGradingSubmission({
      submissionId,
      studentName,
      fileName,
      currentMarks: marks !== null && marks !== undefined ? marks : "",
      currentFeedback: feedback || "",
      maxMarks,
    });
    setGradeMarks(marks !== null && marks !== undefined ? marks : "");
    setGradeFeedback(feedback || "");
    setGradingError(null);
  };

  const handleSaveGrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gradingSubmission) return;

    const numMarks = Number(gradeMarks);
    if (isNaN(numMarks) || numMarks < 0 || numMarks > gradingSubmission.maxMarks) {
      setGradingError(`Score must be a number between 0 and ${gradingSubmission.maxMarks}.`);
      return;
    }

    setGradingSubmitting(true);
    setGradingError(null);

    try {
      await api.put<SubmissionDetail>(
        `/api/submissions/${gradingSubmission.submissionId}/grade`,
        {
          marks: numMarks,
          feedback: gradeFeedback.trim() || null,
        },
        { token }
      );

      const targetStudent = gradingSubmission.studentName;
      const targetMax = gradingSubmission.maxMarks;
      setGradingSubmission(null);
      toast.success(`Evaluation saved for ${targetStudent}: ${numMarks}/${targetMax} pts.`);
      await loadAllData();
    } catch (err: any) {
      setGradingError(err.message || "Failed to save evaluation.");
      toast.error(err.message || "Failed to save grade evaluation.");
    } finally {
      setGradingSubmitting(false);
    }
  };

  const handleDownload = async (submissionId: string) => {
    if (!token) return;
    setDownloadingId(submissionId);
    try {
      const data = await api.get<{ download_url: string }>(
        `/api/submissions/${submissionId}/download`,
        { token }
      );
      if (data.download_url) {
        window.open(data.download_url, "_blank", "noopener,noreferrer");
      }
    } catch (err: any) {
      toast.error(`Download Error: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const assignmentMeta = submissions.length > 0 ? submissions[0] : null;

  const filteredSubmissions = submissions.filter((sub) => {
    const query = searchQuery.toLowerCase();
    const nameMatch =
      (sub.student_name || "").toLowerCase().includes(query) ||
      (sub.student_email || "").toLowerCase().includes(query) ||
      sub.student_id.toLowerCase().includes(query) ||
      sub.file_name.toLowerCase().includes(query);

    const statusMatch =
      statusFilter === "ALL" ||
      (statusFilter === "GRADED" && sub.submission_status === "GRADED") ||
      (statusFilter === "UNGRADED" && sub.submission_status !== "GRADED") ||
      sub.submission_status === statusFilter;

    return nameMatch && statusMatch;
  });

  const filteredGradebook = gradebook.filter((entry) => {
    const query = searchQuery.toLowerCase();
    const match =
      entry.student_name.toLowerCase().includes(query) ||
      (entry.student_email || "").toLowerCase().includes(query) ||
      entry.student_id.toLowerCase().includes(query);

    const statusMatch =
      statusFilter === "ALL" ||
      (statusFilter === "GRADED" && entry.submission_status === "GRADED") ||
      (statusFilter === "UNGRADED" && entry.submission_status !== "GRADED" && entry.submission_status !== "NOT_SUBMITTED") ||
      entry.submission_status === statusFilter;

    return match && statusMatch;
  });

  if (loading || fetching) {
    return (
      <AppLayout>
        <LoadingSpinner message="Loading evaluation dashboard & gradebook..." />
      </AppLayout>
    );
  }

  return (
    <AppLayout
      breadcrumbs={[
        { label: "My Courses", href: "/teacher/courses" },
        {
          label: assignmentMeta?.course_name || "Course",
          href: assignmentMeta?.course_id ? `/teacher/courses/${assignmentMeta.course_id}/assignments` : "/teacher/courses",
        },
        { label: assignmentMeta?.assignment_title || "Submissions & Grading" },
      ]}
    >
      <div className="space-y-6">
        {/* Assignment Info Banner */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="px-2.5 py-0.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono font-semibold">
                  {assignmentId}
                </span>
                {assignmentMeta?.course_name && (
                  <span className="text-xs text-slate-400 font-mono">
                    Course: <span className="text-white font-semibold">{assignmentMeta.course_name}</span>
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                {assignmentMeta?.assignment_title || `Submissions for ${assignmentId}`}
              </h1>
              {assignmentMeta?.assignment_deadline && (
                <p className="text-xs text-slate-400 mt-1 font-mono">
                  Deadline: <span className="text-slate-200">{new Date(assignmentMeta.assignment_deadline).toLocaleString()}</span>
                </p>
              )}
            </div>

            {/* Quick Summary Pill */}
            <div className="flex items-center gap-3">
              <span className="px-3.5 py-1.5 rounded-xl bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold font-mono">
                Max Score: {stats?.max_marks || 100} pts
              </span>
            </div>
          </div>
        </div>

        {/* Statistical Metrics Summary Panel */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Total Students</span>
              <span className="text-lg font-bold text-white mt-1 block font-mono">{stats.total_students}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Submissions</span>
              <span className="text-lg font-bold text-indigo-400 mt-1 block font-mono" id="stats-total-submissions">
                {stats.total_submissions}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Graded</span>
              <span className="text-lg font-bold text-emerald-400 mt-1 block font-mono" id="stats-graded-count">
                {stats.graded_count}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Ungraded</span>
              <span className="text-lg font-bold text-amber-400 mt-1 block font-mono" id="stats-ungraded-count">
                {stats.ungraded_count}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">Average Score</span>
              <span className="text-lg font-bold text-purple-400 mt-1 block font-mono" id="stats-avg-marks">
                {stats.average_marks !== null ? `${stats.average_marks} pts` : "N/A"}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm text-center">
              <span className="text-[10px] uppercase font-semibold text-slate-500 block">High / Low</span>
              <span className="text-sm font-bold text-slate-200 mt-1 block font-mono">
                {stats.highest_marks !== null ? `${stats.highest_marks} / ${stats.lowest_marks}` : "N/A"}
              </span>
            </div>
          </div>
        )}

        {/* View Switcher Tabs & Filter Bar */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                onClick={() => setActiveTab("submissions")}
                id="tab-submissions-btn"
                className={`py-1.5 px-4 rounded-lg font-semibold transition-all ${
                  activeTab === "submissions"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Submissions List ({submissions.length})
              </button>
              <button
                onClick={() => setActiveTab("gradebook")}
                id="tab-gradebook-btn"
                className={`py-1.5 px-4 rounded-lg font-semibold transition-all ${
                  activeTab === "gradebook"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Full Gradebook Matrix ({gradebook.length})
              </button>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
            <div className="w-full sm:w-64">
              <input
                id="teacher-submission-search-input"
                type="text"
                placeholder="Search student or file..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs w-full sm:w-auto overflow-x-auto">
              {["ALL", "GRADED", "UNGRADED"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`py-1 px-3 rounded-lg font-medium transition-all ${
                    statusFilter === st
                      ? "bg-indigo-600 text-white font-semibold shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tab 1: Submissions Table */}
        {activeTab === "submissions" && (
          filteredSubmissions.length === 0 ? (
            <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
              <div className="text-4xl mb-3">📬</div>
              <h3 className="text-lg font-bold text-white mb-1">No Submissions Found</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                {submissions.length === 0
                  ? "No students have submitted deliverables for this assignment yet."
                  : "No submissions match your search query."}
              </p>
            </div>
          ) : (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-mono text-[10px]">
                    <tr>
                      <th className="py-3.5 px-4 font-semibold">Student Name &amp; ID</th>
                      <th className="py-3.5 px-4 font-semibold">Deliverable File</th>
                      <th className="py-3.5 px-4 font-semibold">Status</th>
                      <th className="py-3.5 px-4 font-semibold">Marks &amp; Feedback</th>
                      <th className="py-3.5 px-4 font-semibold">Submitted At</th>
                      <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-medium">
                    {filteredSubmissions.map((s) => (
                      <tr key={s.submission_id} id={`submission-row-${s.submission_id}`} className="hover:bg-slate-800/40 transition-colors">
                        {/* Student Info */}
                        <td className="py-4 px-4">
                          <div className="font-bold text-white text-sm">
                            {s.student_name || "Enrolled Student"}
                          </div>
                          <div className="text-slate-400 text-[11px] font-mono mt-0.5">
                            {s.student_email || s.student_id}
                          </div>
                          {s.resubmission_count > 0 && (
                            <span className="inline-block mt-1 px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-[9px] font-mono font-semibold">
                              Resubmitted (v{s.resubmission_count + 1})
                            </span>
                          )}
                        </td>

                        {/* File Name */}
                        <td className="py-4 px-4 font-mono">
                          <div className="flex items-center gap-1.5 text-slate-200">
                            <span>📄</span>
                            <span className="truncate max-w-[180px]">{s.file_name}</span>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="py-4 px-4">
                          <StatusBadge status={s.submission_status} resubmissionCount={s.resubmission_count} />
                        </td>

                        {/* Marks & Feedback */}
                        <td className="py-4 px-4">
                          {s.marks !== null && s.marks !== undefined ? (
                            <div>
                              <div className="font-bold text-emerald-400 text-sm font-mono">
                                {s.marks} / {stats?.max_marks || 100} pts
                              </div>
                              {s.feedback && (
                                <p className="text-[11px] text-slate-300 mt-0.5 line-clamp-1 italic max-w-xs">
                                  &quot;{s.feedback}&quot;
                                </p>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-500 italic text-[11px]">Ungraded</span>
                          )}
                        </td>

                        {/* Submitted At */}
                        <td className="py-4 px-4 text-slate-300 font-mono text-[11px]">
                          {new Date(s.submitted_at).toLocaleString()}
                        </td>

                        {/* Actions */}
                        <td className="py-4 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => handleDownload(s.submission_id)}
                              disabled={downloadingId === s.submission_id}
                              id={`teacher-download-btn-${s.submission_id}`}
                              className="py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all flex items-center gap-1 disabled:opacity-50"
                              title="Download deliverable file"
                            >
                              <span>📥</span>
                              <span>File</span>
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                handleOpenGradeModal(
                                  s.submission_id,
                                  s.student_name || "Student",
                                  s.file_name,
                                  s.marks,
                                  s.feedback
                                )
                              }
                              id={`grade-submission-btn-${s.submission_id}`}
                              className="py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all flex items-center gap-1"
                            >
                              <span>✏️</span>
                              <span>{s.marks !== null && s.marks !== undefined ? "Regrade" : "Grade"}</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        )}

        {/* Tab 2: Full Gradebook Matrix */}
        {activeTab === "gradebook" && (
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-mono text-[10px]">
                  <tr>
                    <th className="py-3.5 px-4 font-semibold">Student</th>
                    <th className="py-3.5 px-4 font-semibold">Status</th>
                    <th className="py-3.5 px-4 font-semibold">File Deliverable</th>
                    <th className="py-3.5 px-4 font-semibold">Awarded Score</th>
                    <th className="py-3.5 px-4 font-semibold">Feedback</th>
                    <th className="py-3.5 px-4 font-semibold text-right">Evaluation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-medium">
                  {filteredGradebook.map((entry) => (
                    <tr key={entry.student_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-4 px-4">
                        <div className="font-bold text-white text-sm">{entry.student_name}</div>
                        <div className="text-slate-400 text-[11px] font-mono">{entry.student_email || entry.student_id}</div>
                      </td>

                      <td className="py-4 px-4">
                        <StatusBadge status={entry.submission_status} resubmissionCount={entry.resubmission_count} />
                      </td>

                      <td className="py-4 px-4 font-mono text-slate-300">
                        {entry.file_name ? (
                          <div className="flex items-center gap-1">
                            <span>📎</span>
                            <span className="truncate max-w-[150px]">{entry.file_name}</span>
                          </div>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      <td className="py-4 px-4 font-mono">
                        {entry.marks !== null && entry.marks !== undefined ? (
                          <span className="font-bold text-emerald-400 text-sm">
                            {entry.marks} / {stats?.max_marks || 100}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      <td className="py-4 px-4 text-slate-300 max-w-xs truncate">
                        {entry.feedback || <span className="text-slate-600">—</span>}
                      </td>

                      <td className="py-4 px-4 text-right">
                        {entry.submission_id ? (
                          <button
                            type="button"
                            onClick={() =>
                              handleOpenGradeModal(
                                entry.submission_id!,
                                entry.student_name,
                                entry.file_name || "Deliverable",
                                entry.marks,
                                entry.feedback
                              )
                            }
                            className="py-1 px-3 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/30 transition-all"
                          >
                            {entry.marks !== null ? "Edit Grade" : "Grade"}
                          </button>
                        ) : (
                          <span className="text-slate-500 text-[11px] italic">Not Submitted</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Grading Modal */}
        {gradingSubmission && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 sm:p-8 shadow-2xl relative">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span>📝</span> Evaluate Deliverable
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Student: <strong className="text-white">{gradingSubmission.studentName}</strong> • File: <span className="font-mono text-indigo-300">{gradingSubmission.fileName}</span>
                  </p>
                </div>
                <button
                  onClick={() => setGradingSubmission(null)}
                  className="text-slate-400 hover:text-white text-sm p-1 rounded-lg hover:bg-slate-800"
                >
                  ✕
                </button>
              </div>

              {gradingError && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                  {gradingError}
                </div>
              )}

              <form onSubmit={handleSaveGrade} className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                      Awarded Marks *
                    </label>
                    <span className="text-xs text-slate-400 font-mono">
                      Max: <strong className="text-indigo-400">{gradingSubmission.maxMarks} pts</strong>
                    </span>
                  </div>
                  <input
                    id="grading-marks-input"
                    type="number"
                    step="0.5"
                    min="0"
                    max={gradingSubmission.maxMarks}
                    required
                    value={gradeMarks}
                    onChange={(e) => setGradeMarks(e.target.value)}
                    placeholder={`0 to ${gradingSubmission.maxMarks}`}
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Constructive Feedback &amp; Comments
                  </label>
                  <textarea
                    id="grading-feedback-input"
                    rows={4}
                    value={gradeFeedback}
                    onChange={(e) => setGradeFeedback(e.target.value)}
                    placeholder="Provide specific feedback on criteria, strengths, and areas for improvement..."
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setGradingSubmission(null)}
                    className="py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    id="submit-grade-btn"
                    disabled={gradingSubmitting}
                    className="py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-2"
                  >
                    {gradingSubmitting ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Saving Grade...</span>
                      </>
                    ) : (
                      <>
                        <span>💾</span>
                        <span>Save Evaluation</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
