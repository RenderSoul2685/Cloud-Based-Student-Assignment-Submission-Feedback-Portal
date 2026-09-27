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

interface Course {
  course_id: string;
  course_name: string;
  description?: string;
  teacher_id: string;
}

export default function TeacherAssignmentsPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = use(params);
  const router = useRouter();
  const { user, profile, token, loading } = useAuth();
  const toast = useToast();

  const [course, setCourse] = useState<Course | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [fetching, setFetching] = useState(true);

  // Create modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [maxMarks, setMaxMarks] = useState<number>(100);
  const [allowedTypes, setAllowedTypes] = useState("pdf,docx,zip");
  const [maxFileSizeMb, setMaxFileSizeMb] = useState<number>(20);
  const [allowLateSubmission, setAllowLateSubmission] = useState<boolean>(true);
  const [resubmissionAllowed, setResubmissionAllowed] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Edit modal state
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editDeadline, setEditDeadline] = useState("");
  const [editMaxMarks, setEditMaxMarks] = useState<number>(100);
  const [editAllowLate, setEditAllowLate] = useState<boolean>(true);
  const [editAllowResubmit, setEditAllowResubmit] = useState<boolean>(true);
  const [editSubmitting, setEditSubmitting] = useState(false);

  // Route Guard
  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace("/login");
      } else if (profile && profile.role !== "TEACHER" && profile.role !== "ADMIN") {
        router.replace("/dashboard");
      }
    }
  }, [user, profile, loading, router]);

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
    } catch (err: any) {
      toast.error(err.message || "Failed to load course assignments.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token && profile && (profile.role === "TEACHER" || profile.role === "ADMIN")) {
      loadData();
    }
  }, [token, profile, courseId]);

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!title.trim() || !description.trim() || !deadline) {
      setFormError("Please fill out all required fields.");
      return;
    }

    const selectedDeadline = new Date(deadline);
    if (selectedDeadline <= new Date()) {
      setFormError("Deadline must be set to a future date and time.");
      return;
    }

    setSubmitting(true);
    try {
      const data = await api.post<Assignment>(
        `/api/courses/${courseId}/assignments`,
        {
          title: title.trim(),
          description: description.trim(),
          deadline: selectedDeadline.toISOString(),
          max_marks: Number(maxMarks),
          allowed_file_types: allowedTypes.trim(),
          max_file_size_mb: Number(maxFileSizeMb),
          allow_late_submission: allowLateSubmission,
          resubmission_allowed: resubmissionAllowed,
        },
        { token }
      );

      setTitle("");
      setDescription("");
      setDeadline("");
      setAllowLateSubmission(true);
      setResubmissionAllowed(true);
      setIsCreateOpen(false);
      toast.success(`Assignment "${data.title}" successfully created!`);
      await loadData();
    } catch (err: any) {
      setFormError(err.message || "An error occurred while creating the assignment.");
      toast.error(err.message || "Failed to create assignment.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenEdit = (assignment: Assignment) => {
    setEditingAssignment(assignment);
    setEditTitle(assignment.title);
    setEditDescription(assignment.description);
    setEditMaxMarks(assignment.max_marks);
    setEditAllowLate(assignment.allow_late_submission !== false);
    setEditAllowResubmit(assignment.resubmission_allowed !== false);

    try {
      const d = new Date(assignment.deadline);
      const tzOffset = d.getTimezoneOffset() * 60000;
      const localISOTime = new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
      setEditDeadline(localISOTime);
    } catch {
      setEditDeadline("");
    }
  };

  const handleUpdateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAssignment) return;
    setFormError(null);
    setEditSubmitting(true);

    try {
      const selectedDeadline = new Date(editDeadline);
      const data = await api.put<Assignment>(
        `/api/courses/${courseId}/assignments/${editingAssignment.assignment_id}`,
        {
          title: editTitle.trim(),
          description: editDescription.trim(),
          deadline: selectedDeadline.toISOString(),
          max_marks: Number(editMaxMarks),
          allow_late_submission: editAllowLate,
          resubmission_allowed: editAllowResubmit,
        },
        { token }
      );

      setEditingAssignment(null);
      toast.success(`Assignment "${data.title}" updated successfully!`);
      await loadData();
    } catch (err: any) {
      setFormError(err.message || "Failed to update assignment.");
      toast.error(err.message || "Failed to update assignment.");
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDeleteAssignment = async (assignmentId: string, title: string) => {
    if (
      !window.confirm(
        `Are you sure you want to delete assignment "${title}"?\n\nNote: If student submissions exist, it will be soft-deleted to preserve submission and grading records.`
      )
    ) {
      return;
    }

    try {
      const data = await api.delete<{ message: string }>(
        `/api/courses/${courseId}/assignments/${assignmentId}`,
        { token }
      );

      toast.success(data.message || "Assignment removed.");
      await loadData();
    } catch (err: any) {
      toast.error(`Error deleting assignment: ${err.message}`);
    }
  };

  if (loading || fetching) {
    return (
      <AppLayout>
        <LoadingSpinner message="Loading course assignment deliverables..." />
      </AppLayout>
    );
  }

  return (
    <AppLayout
      breadcrumbs={[
        { label: "My Courses", href: "/teacher/courses" },
        { label: course?.course_name || "Assignments" },
      ]}
    >
      <div className="space-y-6">
        {/* Course Banner */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono font-semibold">
              {course?.course_id}
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold text-white mt-2">{course?.course_name}</h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              {course?.description || "Course Assignment and Submission Portal"}
            </p>
          </div>
          <div className="flex flex-col sm:items-end gap-3">
            <div className="text-right">
              <span className="text-xs text-slate-400">Total Assignments: </span>
              <span className="text-base font-bold text-indigo-400">{assignments.length}</span>
            </div>
            <button
              onClick={() => {
                setIsCreateOpen(true);
                setFormError(null);
              }}
              id="create-assignment-modal-btn"
              className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-1.5"
            >
              <span>+</span>
              <span>New Assignment</span>
            </button>
          </div>
        </div>

        {/* Assignments List */}
        {assignments.length === 0 ? (
          <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
            <div className="text-4xl mb-3">📝</div>
            <h3 className="text-lg font-bold text-white mb-1">No Assignments Yet</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
              Create assignments with deadline controls, allowed file formats, and points for students.
            </p>
            <button
              onClick={() => setIsCreateOpen(true)}
              className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 transition-all"
            >
              + Create First Assignment
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {assignments.map((a) => {
              const deadlineDate = new Date(a.deadline);
              const isPast = deadlineDate <= new Date();

              return (
                <div
                  key={a.assignment_id}
                  id={`teacher-assignment-card-${a.assignment_id}`}
                  className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 backdrop-blur-sm shadow-md transition-all flex flex-col md:flex-row md:items-center justify-between gap-6"
                >
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 text-[10px] font-mono">
                        {a.assignment_id}
                      </span>
                      <StatusBadge status={isPast ? "LATE" : "SUBMITTED"} />
                      <span className="text-xs text-slate-400">
                        Max Score: <strong className="text-white">{a.max_marks} pts</strong>
                      </span>
                      {a.allow_late_submission === false && (
                        <span className="px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-300 border border-rose-500/20 text-[10px]">
                          Late Submissions Blocked
                        </span>
                      )}
                      {a.resubmission_allowed === false && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[10px]">
                          Single Attempt Only
                        </span>
                      )}
                    </div>

                    <h3 className="text-lg font-bold text-white mb-1">{a.title}</h3>
                    <p className="text-xs text-slate-300 line-clamp-2 mb-3">{a.description}</p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 font-mono">
                      <div>
                        📅 Due:{" "}
                        <span className={isPast ? "text-rose-400 font-semibold" : "text-slate-200"}>
                          {deadlineDate.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        📎 Formats: <span className="text-slate-200">{a.allowed_file_types}</span>
                      </div>
                      <div>
                        💾 Max Size: <span className="text-slate-200">{a.max_file_size_mb} MB</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center flex-shrink-0">
                    <Link
                      href={`/teacher/assignments/${a.assignment_id}/submissions`}
                      id={`view-submissions-link-${a.assignment_id}`}
                      className="py-2 px-3.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 hover:text-white text-xs font-semibold border border-indigo-500/30 transition-all flex items-center gap-1.5"
                    >
                      <span>👥</span>
                      <span>View Submissions</span>
                    </Link>
                    <button
                      onClick={() => handleOpenEdit(a)}
                      id={`edit-assignment-${a.assignment_id}`}
                      className="py-2 px-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteAssignment(a.assignment_id, a.title)}
                      id={`delete-assignment-${a.assignment_id}`}
                      className="py-2 px-3.5 rounded-xl bg-rose-600/10 hover:bg-rose-600 text-rose-400 hover:text-white text-xs font-semibold border border-rose-500/30 transition-all"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Create Assignment Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 sm:p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>✨</span> New Assignment Task
                </h3>
                <button onClick={() => setIsCreateOpen(false)} className="text-slate-400 hover:text-white text-sm">✕</button>
              </div>

              {formError && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                  {formError}
                </div>
              )}

              <form onSubmit={handleCreateAssignment} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Assignment Title *
                  </label>
                  <input
                    id="assignment-title-input"
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Distributed Consensus Engine"
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Description &amp; Deliverable Guidelines *
                  </label>
                  <textarea
                    id="assignment-desc-input"
                    rows={3}
                    required
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Provide detailed instructions and grading rubrics..."
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Deadline (Date &amp; Time) *
                    </label>
                    <input
                      id="assignment-deadline-input"
                      type="datetime-local"
                      required
                      value={deadline}
                      onChange={(e) => setDeadline(e.target.value)}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Maximum Score (Points) *
                    </label>
                    <input
                      id="assignment-marks-input"
                      type="number"
                      required
                      min={1}
                      max={1000}
                      value={maxMarks}
                      onChange={(e) => setMaxMarks(Number(e.target.value))}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Allowed File Extensions
                    </label>
                    <input
                      id="assignment-types-input"
                      type="text"
                      required
                      value={allowedTypes}
                      onChange={(e) => setAllowedTypes(e.target.value)}
                      placeholder="pdf,docx,zip,png,jpg"
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Max File Size (MB)
                    </label>
                    <input
                      id="assignment-filesize-input"
                      type="number"
                      required
                      min={1}
                      max={50}
                      value={maxFileSizeMb}
                      onChange={(e) => setMaxFileSizeMb(Number(e.target.value))}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* Submission Policies */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                  <span className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Submission Policies
                  </span>
                  <label className="flex items-center gap-3 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allowLateSubmission}
                      onChange={(e) => setAllowLateSubmission(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                    <span>Allow Late Submissions (flagged with LATE status)</span>
                  </label>
                  <label className="flex items-center gap-3 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={resubmissionAllowed}
                      onChange={(e) => setResubmissionAllowed(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                    <span>Allow Resubmissions (students can update file before grading)</span>
                  </label>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsCreateOpen(false)}
                    className="py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    id="submit-create-assignment-btn"
                    disabled={submitting}
                    className="py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
                  >
                    {submitting ? "Publishing..." : "Publish Assignment"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Edit Assignment Modal */}
        {editingAssignment && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 sm:p-8 shadow-2xl relative">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>✏️</span> Edit Assignment
                </h3>
                <button onClick={() => setEditingAssignment(null)} className="text-slate-400 hover:text-white text-sm">✕</button>
              </div>

              {formError && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                  {formError}
                </div>
              )}

              <form onSubmit={handleUpdateAssignment} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Title
                  </label>
                  <input
                    type="text"
                    required
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Description
                  </label>
                  <textarea
                    rows={3}
                    required
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Deadline
                    </label>
                    <input
                      type="datetime-local"
                      required
                      value={editDeadline}
                      onChange={(e) => setEditDeadline(e.target.value)}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                      Max Marks
                    </label>
                    <input
                      type="number"
                      required
                      min={1}
                      value={editMaxMarks}
                      onChange={(e) => setEditMaxMarks(Number(e.target.value))}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* Edit Policies */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                  <span className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Submission Policies
                  </span>
                  <label className="flex items-center gap-3 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editAllowLate}
                      onChange={(e) => setEditAllowLate(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                    <span>Allow Late Submissions</span>
                  </label>
                  <label className="flex items-center gap-3 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editAllowResubmit}
                      onChange={(e) => setEditAllowResubmit(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                    <span>Allow Resubmissions</span>
                  </label>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setEditingAssignment(null)}
                    className="py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={editSubmitting}
                    className="py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
                  >
                    {editSubmitting ? "Saving..." : "Save Changes"}
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
