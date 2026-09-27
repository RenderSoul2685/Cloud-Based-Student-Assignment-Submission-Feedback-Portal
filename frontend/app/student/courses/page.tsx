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

export default function StudentCoursesPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [courses, setCourses] = useState<Course[]>([]);
  const [fetching, setFetching] = useState(true);

  const fetchCourses = async () => {
    if (!token) return;
    setFetching(true);
    try {
      const data = await api.get<Course[]>("/api/courses", { token });
      setCourses(data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load courses catalog.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchCourses();
    }
  }, [token]);

  return (
    <AppLayout
      requiredRole="STUDENT"
      breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: "Course Catalog" },
      ]}
    >
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 border bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-mono">
          <span>🎓</span> Course Catalog &amp; Assignments
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          Academic Courses &amp; Modules
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
          Select a course to view assignment requirements, submission deadlines, and grading criteria.
        </p>
      </div>

      {fetching ? (
        <LoadingSpinner message="Loading course catalog..." />
      ) : courses.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <div className="text-4xl mb-3">📚</div>
          <h2 className="text-lg font-bold text-white mb-1">No Courses Available</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            There are currently no active courses registered on the portal. Please check back later.
          </p>
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
                <span className="text-xs text-slate-500 font-mono text-[11px]">
                  ID: {c.teacher_id.slice(0, 10)}...
                </span>
                <Link
                  href={`/student/courses/${c.course_id}/assignments`}
                  id={`student-view-assignments-${c.course_id}`}
                  className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-1.5"
                >
                  <span>View Assignments</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
