"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/apiClient";
import AppLayout from "@/components/AppLayout";
import LoadingSpinner from "@/components/LoadingSpinner";

interface Course {
  course_id: string;
  course_name: string;
  description?: string;
  teacher_id: string;
  created_at: string;
}

export default function TeacherCoursesPage() {
  const { profile, token } = useAuth();
  const toast = useToast();

  const [courses, setCourses] = useState<Course[]>([]);
  const [fetching, setFetching] = useState(true);

  // New course modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newCourseName, setNewCourseName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const loadCourses = async () => {
    if (!token) return;
    setFetching(true);
    try {
      const data = await api.get<Course[]>("/api/courses/mine", { token });
      setCourses(data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load instructor courses.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token && profile && (profile.role === "TEACHER" || profile.role === "ADMIN")) {
      loadCourses();
    }
  }, [token, profile]);

  const handleCreateCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCourseName.trim()) {
      toast.warning("Course name is required.");
      return;
    }

    setCreating(true);
    try {
      await api.post(
        "/api/courses",
        {
          course_name: newCourseName.trim(),
          description: newDescription.trim(),
        },
        { token }
      );

      toast.success(`Course "${newCourseName.trim()}" created successfully!`);
      setNewCourseName("");
      setNewDescription("");
      setIsModalOpen(false);
      await loadCourses();
    } catch (err: any) {
      toast.error(err.message || "Course creation failed.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <AppLayout
      requiredRole={["TEACHER", "ADMIN"]}
      breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: "Course Management" },
      ]}
      actions={
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          id="create-course-header-btn"
          className="py-1.5 px-3.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/30 transition-all flex items-center gap-1.5"
        >
          <span>＋</span>
          <span>New Course</span>
        </button>
      }
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 border bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-mono">
            <span>📚</span> Instructor Course Hub
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Assigned Teaching Courses
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
            Create academic courses, post assignment modules, set deadlines, and evaluate student deliverable submissions.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          id="create-course-btn"
          className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 flex-shrink-0"
        >
          <span>＋</span>
          <span>Create New Course</span>
        </button>
      </div>

      {/* Course List */}
      {fetching ? (
        <LoadingSpinner message="Loading your courses..." />
      ) : courses.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <div className="text-4xl mb-3">📚</div>
          <h2 className="text-lg font-bold text-white mb-1">No Courses Found</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-4">
            You have not created any courses yet. Get started by clicking the button below.
          </p>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="py-2 px-4 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition-all"
          >
            Create Your First Course
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((c) => (
            <div
              key={c.course_id}
              className="bg-slate-900/80 border border-slate-800 hover:border-indigo-500/40 rounded-2xl p-6 backdrop-blur-sm shadow-xl flex flex-col justify-between transition-all group"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <span className="px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[10px] font-mono font-semibold">
                    {c.course_id}
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-white group-hover:text-indigo-300 transition-colors mb-2">
                  {c.course_name}
                </h2>
                <p className="text-xs text-slate-400 line-clamp-3 mb-6">
                  {c.description || "No course description provided."}
                </p>
              </div>

              <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
                <span className="text-xs text-slate-500 font-mono text-[11px]">Instructor: You</span>
                <Link
                  href={`/teacher/courses/${c.course_id}/assignments`}
                  id={`view-assignments-link-${c.course_id}`}
                  className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-1.5"
                >
                  <span>Manage Assignments</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Course Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>➕</span> Create Academic Course
              </h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCourse} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Course Name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="create-course-name-input"
                  type="text"
                  required
                  placeholder="e.g. CS401: Cloud Computing"
                  value={newCourseName}
                  onChange={(e) => setNewCourseName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Course Description
                </label>
                <textarea
                  id="create-course-desc-input"
                  rows={3}
                  placeholder="Brief overview of course deliverables..."
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  id="submit-create-course-btn"
                  className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Create Course"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
