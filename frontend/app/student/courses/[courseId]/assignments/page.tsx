"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/apiClient";
import AppLayout from "@/components/AppLayout";
import LoadingSpinner from "@/components/LoadingSpinner";
import StatusBadge from "@/components/StatusBadge";

interface Assignment {
  assignment_id: string;
  course_id: string;
  title: string;
  description: string;
  deadline: string;
  max_marks: number;
  allowed_file_types: string;
  max_file_size_mb: number;
  allow_late_submission?: boolean;
  resubmission_allowed?: boolean;
  created_by: string;
  created_at: string;
  is_deleted?: boolean;
}

interface Submission {
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
}

interface Course {
  course_id: string;
  course_name: string;
  description?: string;
  teacher_id: string;
}

export default function StudentAssignmentsPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = use(params);
  const { token } = useAuth();
  const toast = useToast();

  const [course, setCourse] = useState<Course | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [submissionsMap, setSubmissionsMap] = useState<Record<string, Submission>>({});
  const [fetching, setFetching] = useState(true);

  // File upload state per assignment_id
  const [selectedFiles, setSelectedFiles] = useState<Record<string, File>>({});
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<Record<string, string>>({});
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [showResubmitMap, setShowResubmitMap] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    if (!token) return;
    setFetching(true);
    try {
      // 1. Fetch Course details
      const courseData = await api.get<Course>(`/api/courses/${courseId}`, { token });
      setCourse(courseData);

      // 2. Fetch Assignments
      const assignData = await api.get<Assignment[]>(`/api/courses/${courseId}/assignments`, { token });
      setAssignments(assignData);

      // 3. Fetch Student's own submissions
      try {
        const subsData = await api.get<Submission[]>("/api/submissions/me", { token });
        const map: Record<string, Submission> = {};
        for (const s of subsData) {
          map[s.assignment_id] = s;
        }
        setSubmissionsMap(map);
      } catch {
        // non-blocking
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load assignments.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadData();
    }
  }, [token, courseId]);

  const handleFileChange = (assignmentId: string, file: File | null) => {
    setUploadErrors((prev) => ({ ...prev, [assignmentId]: "" }));
    if (!file) {
      setSelectedFiles((prev) => {
        const copy = { ...prev };
        delete copy[assignmentId];
        return copy;
      });
      return;
    }
    setSelectedFiles((prev) => ({ ...prev, [assignmentId]: file }));
  };

  const handleSubmit = async (assignment: Assignment) => {
    const file = selectedFiles[assignment.assignment_id];
    if (!file) {
      setUploadErrors((prev) => ({
        ...prev,
        [assignment.assignment_id]: "Please select a file to submit.",
      }));
      toast.warning("Please select a file to submit.");
      return;
    }

    // Client-side extension validation
    const allowedExts = assignment.allowed_file_types
      .split(",")
      .map((e) => e.trim().toLowerCase().replace(".", ""));
    const fileExt = file.name.split(".").pop()?.toLowerCase() || "";
    if (!allowedExts.includes(fileExt)) {
      const msg = `Invalid file format .${fileExt}. Allowed formats: ${assignment.allowed_file_types}`;
      setUploadErrors((prev) => ({
        ...prev,
        [assignment.assignment_id]: msg,
      }));
      toast.error(msg);
      return;
    }

    // Client-side file size validation
    const maxBytes = assignment.max_file_size_mb * 1024 * 1024;
    if (file.size > maxBytes) {
      const msg = `File size exceeds ${assignment.max_file_size_mb} MB limit.`;
      setUploadErrors((prev) => ({
        ...prev,
        [assignment.assignment_id]: msg,
      }));
      toast.error(msg);
      return;
    }

    setUploadingId(assignment.assignment_id);
    setUploadErrors((prev) => ({ ...prev, [assignment.assignment_id]: "" }));

    try {
      const formData = new FormData();
      formData.append("file", file);

      const updatedSub = await api.post<Submission>(
        `/api/assignments/${assignment.assignment_id}/submit`,
        formData,
        { token }
      );

      setSubmissionsMap((prev) => ({
        ...prev,
        [assignment.assignment_id]: updatedSub,
      }));

      // Reset file input state
      setSelectedFiles((prev) => {
        const copy = { ...prev };
        delete copy[assignment.assignment_id];
        return copy;
      });
      setShowResubmitMap((prev) => ({ ...prev, [assignment.assignment_id]: false }));

      if (updatedSub.resubmission_count > 0) {
        toast.success(`Resubmission (v${updatedSub.resubmission_count + 1}) uploaded! Prior grade reset until re-evaluated.`);
      } else {
        toast.success(`Assignment "${assignment.title}" submitted successfully! Status: ${updatedSub.submission_status}`);
      }
    } catch (err: any) {
      setUploadErrors((prev) => ({
        ...prev,
        [assignment.assignment_id]: err.message || "Failed to submit assignment.",
      }));
      toast.error(err.message || "Failed to submit assignment.");
    } finally {
      setUploadingId(null);
    }
  };

  const handleDownloadFile = async (submissionId: string) => {
    if (!token) return;
    setDownloadingId(submissionId);
    try {
      const data = await api.get<{ download_url: string }>(`/api/submissions/${submissionId}/download`, { token });
      if (data.download_url) {
        window.open(data.download_url, "_blank", "noopener,noreferrer");
      }
    } catch (err: any) {
      toast.error(`Error opening file: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <AppLayout
      requiredRole="STUDENT"
      breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: "My Courses", href: "/student/courses" },
        { label: course?.course_name || courseId },
      ]}
      actions={
        <Link
          href="/student/submissions"
          id="header-my-submissions-btn"
          className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 py-1 px-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 transition-all flex items-center gap-1.5"
        >
          <span>📋</span>
          <span>My Submissions</span>
        </Link>
      }
    >
      {/* Course Banner */}
      <div className="mb-8 p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/30 to-slate-900 border border-slate-800 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono font-semibold">
              {course?.course_id || courseId}
            </span>
            <h1 className="text-2xl font-bold text-white mt-2">{course?.course_name || "Course Assignments"}</h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              {course?.description || "Course Assignment and Deliverables Portal"}
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-400">Available Assignments: </span>
            <span className="text-base font-bold text-indigo-400 font-mono">{assignments.length}</span>
          </div>
        </div>
      </div>

      {fetching ? (
        <LoadingSpinner message="Loading course assignments..." />
      ) : assignments.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <div className="text-4xl mb-3">📋</div>
          <h2 className="text-lg font-bold text-white mb-1">No Active Assignments</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Your instructor has not posted any assignments for this course yet.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {assignments.map((a) => {
            const deadlineDate = new Date(a.deadline);
            const now = new Date();
            const isPast = deadlineDate <= now;
            const diffHours = Math.round((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60));
            const diffDays = Math.round(diffHours / 24);

            const sub = submissionsMap[a.assignment_id];
            const isSubmittingThis = uploadingId === a.assignment_id;
            const uploadError = uploadErrors[a.assignment_id];
            const selectedFile = selectedFiles[a.assignment_id];
            const allowLate = a.allow_late_submission !== false;
            const allowResubmit = a.resubmission_allowed !== false;
            const showResubmit = showResubmitMap[a.assignment_id];

            return (
              <div
                key={a.assignment_id}
                id={`assignment-card-${a.assignment_id}`}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 backdrop-blur-sm shadow-md transition-all"
              >
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                  {/* Assignment Information */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 text-[10px] font-mono">
                        {a.assignment_id}
                      </span>

                      {/* Due status badge */}
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                          isPast
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : diffHours <= 24
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        }`}
                      >
                        {isPast
                          ? "Deadline Passed"
                          : diffHours <= 24
                          ? "Due Soon (< 24 hrs)"
                          : `Due in ${diffDays} day${diffDays === 1 ? "" : "s"}`}
                      </span>

                      {/* Submission status badge */}
                      {sub && (
                        <StatusBadge
                          status={sub.submission_status}
                          resubmissionCount={sub.resubmission_count}
                        />
                      )}

                      <span className="text-xs text-slate-400 ml-auto lg:ml-0">
                        Max Score: <strong className="text-white font-mono">{a.max_marks} pts</strong>
                      </span>
                    </div>

                    <h2 className="text-lg font-bold text-white mb-1.5">{a.title}</h2>
                    <p className="text-xs text-slate-300 mb-4 whitespace-pre-wrap leading-relaxed">
                      {a.description}
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs font-mono mb-4">
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Deadline:</span>
                        <span className={isPast ? "text-rose-400 font-semibold" : "text-slate-200 font-medium"}>
                          {deadlineDate.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Allowed Formats:</span>
                        <span className="text-indigo-300 font-medium">{a.allowed_file_types}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Max File Size:</span>
                        <span className="text-indigo-300 font-medium">{a.max_file_size_mb} MB</span>
                      </div>
                    </div>

                    {/* Existing Submission Details */}
                    {sub && (
                      <div className="p-4 rounded-xl bg-slate-900/90 border border-indigo-500/20 mb-4 space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-indigo-400">📄</span>
                              <span className="text-xs font-semibold text-white truncate max-w-xs sm:max-w-md">
                                {sub.file_name}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-1 font-mono">
                              Submitted on: {new Date(sub.submitted_at).toLocaleString()}
                              {sub.resubmission_count > 0 && (
                                <span className="text-indigo-300 ml-2">
                                  • Resubmission count: {sub.resubmission_count}
                                </span>
                              )}
                            </p>
                          </div>

                          <div className="flex items-center gap-2 flex-shrink-0">
                            <button
                              type="button"
                              onClick={() => handleDownloadFile(sub.submission_id)}
                              disabled={downloadingId === sub.submission_id}
                              id={`download-submission-btn-${a.assignment_id}`}
                              className="py-1.5 px-3 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/40 transition-all flex items-center gap-1.5 disabled:opacity-50"
                            >
                              {downloadingId === sub.submission_id ? (
                                <>
                                  <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></div>
                                  <span>Opening...</span>
                                </>
                              ) : (
                                <>
                                  <span>📥</span>
                                  <span>View File</span>
                                </>
                              )}
                            </button>

                            {allowResubmit && !showResubmit && (
                              <button
                                type="button"
                                onClick={() => setShowResubmitMap((prev) => ({ ...prev, [a.assignment_id]: true }))}
                                id={`open-resubmit-btn-${a.assignment_id}`}
                                className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all"
                              >
                                🔄 Resubmit
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Evaluation / Grade Display */}
                        {sub.submission_status === "GRADED" && sub.marks !== null && sub.marks !== undefined ? (
                          <div className="p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/30">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
                                <span>⭐</span> Instructor Evaluation
                              </span>
                              <span className="text-sm font-bold text-emerald-400 font-mono" id={`grade-display-${a.assignment_id}`}>
                                {sub.marks} / {a.max_marks} pts
                              </span>
                            </div>
                            {sub.feedback && (
                              <div className="mt-2 text-xs text-slate-200 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                                <span className="text-slate-400 block text-[10px] uppercase font-semibold mb-0.5">Feedback:</span>
                                <p className="italic">&quot;{sub.feedback}&quot;</p>
                              </div>
                            )}
                          </div>
                        ) : sub.resubmission_count > 0 && sub.marks === null ? (
                          <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs">
                            ℹ️ Resubmission deliverable recorded. Previous evaluation reset and awaiting instructor re-grading.
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>

                  {/* Submission Upload / Action Box */}
                  <div className="w-full lg:w-80 flex flex-col justify-between p-4 rounded-2xl bg-slate-950/80 border border-slate-800/80 flex-shrink-0">
                    {isPast && !allowLate && !sub ? (
                      <div className="text-center py-6">
                        <div className="text-2xl mb-2">🔒</div>
                        <h4 className="text-xs font-bold text-rose-400 uppercase tracking-wider">Submissions Closed</h4>
                        <p className="text-[11px] text-slate-500 mt-1">
                          The deadline for this assignment has passed and late submissions are disabled.
                        </p>
                      </div>
                    ) : sub && !allowResubmit ? (
                      <div className="text-center py-6">
                        <div className="text-2xl mb-2">🔒</div>
                        <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Submitted</h4>
                        <p className="text-[11px] text-slate-500 mt-1">
                          Resubmissions are disabled for this assignment.
                        </p>
                      </div>
                    ) : sub && !showResubmit ? (
                      <div className="text-center py-4">
                        <span className="text-xs font-bold text-emerald-400">Deliverable Recorded</span>
                        <p className="text-[11px] text-slate-400 mt-1 mb-3">
                          You can replace your submission prior to grading or resubmit a revised version.
                        </p>
                        <button
                          type="button"
                          onClick={() => setShowResubmitMap((prev) => ({ ...prev, [a.assignment_id]: true }))}
                          className="w-full py-2 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all"
                        >
                          Resubmit New File
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white uppercase tracking-wider">
                            {sub ? "Resubmit File" : "Submit File"}
                          </span>
                          {sub && (
                            <button
                              type="button"
                              onClick={() => {
                                setShowResubmitMap((prev) => ({ ...prev, [a.assignment_id]: false }));
                                setSelectedFiles((prev) => {
                                  const copy = { ...prev };
                                  delete copy[a.assignment_id];
                                  return copy;
                                });
                              }}
                              className="text-[11px] text-slate-400 hover:text-white"
                            >
                              Cancel
                            </button>
                          )}
                        </div>

                        {isPast && allowLate && (
                          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px]">
                            ⚠️ Notice: Submission is past the deadline and will be flagged as <strong>LATE</strong>.
                          </div>
                        )}

                        {uploadError && (
                          <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px]">
                            {uploadError}
                          </div>
                        )}

                        {/* File input */}
                        <div>
                          <label
                            htmlFor={`file-input-${a.assignment_id}`}
                            className="border border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-3 flex flex-col items-center justify-center cursor-pointer transition-colors bg-slate-900/50"
                          >
                            <span className="text-lg mb-1">📤</span>
                            <span className="text-xs font-semibold text-slate-200 text-center truncate max-w-full px-2">
                              {selectedFile ? selectedFile.name : "Choose deliverable file"}
                            </span>
                            <span className="text-[10px] text-slate-500 mt-0.5 font-mono">
                              {selectedFile
                                ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB`
                                : `Max ${a.max_file_size_mb} MB (${a.allowed_file_types})`}
                            </span>
                          </label>
                          <input
                            id={`file-input-${a.assignment_id}`}
                            type="file"
                            className="hidden"
                            accept={a.allowed_file_types
                              .split(",")
                              .map((t) => (t.startsWith(".") ? t : `.${t.trim()}`))
                              .join(",")}
                            onChange={(e) => handleFileChange(a.assignment_id, e.target.files?.[0] || null)}
                          />
                        </div>

                        <button
                          type="button"
                          onClick={() => handleSubmit(a)}
                          disabled={isSubmittingThis || !selectedFile}
                          id={`submit-assignment-btn-${a.assignment_id}`}
                          className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                          {isSubmittingThis ? (
                            <>
                              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                              <span>Uploading Deliverable...</span>
                            </>
                          ) : (
                            <>
                              <span>🚀</span>
                              <span>{sub ? "Upload Resubmission" : "Submit Assignment"}</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
