"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/apiClient";
import AppLayout from "@/components/AppLayout";
import LoadingSpinner from "@/components/LoadingSpinner";
import StatusBadge from "@/components/StatusBadge";

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
  assignment_title?: string | null;
  assignment_deadline?: string | null;
  max_marks?: number | null;
  course_name?: string | null;
}

export default function StudentSubmissionsPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [submissions, setSubmissions] = useState<SubmissionDetail[]>([]);
  const [fetching, setFetching] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadSubmissions = async () => {
    if (!token) return;
    setFetching(true);
    try {
      const data = await api.get<SubmissionDetail[]>("/api/submissions/me", { token });
      data.sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime());
      setSubmissions(data);
    } catch (err: any) {
      toast.error(err.message || "Failed to load submissions list.");
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadSubmissions();
    }
  }, [token]);

  const handleDownload = async (submissionId: string) => {
    if (!token) return;
    setDownloadingId(submissionId);
    try {
      const data = await api.get<{ download_url: string }>(`/api/submissions/${submissionId}/download`, { token });
      if (data.download_url) {
        window.open(data.download_url, "_blank", "noopener,noreferrer");
      }
    } catch (err: any) {
      toast.error(`Download error: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredSubmissions = submissions.filter((sub) => {
    const titleMatch =
      (sub.assignment_title || sub.assignment_id).toLowerCase().includes(searchQuery.toLowerCase()) ||
      (sub.course_name || sub.course_id).toLowerCase().includes(searchQuery.toLowerCase()) ||
      sub.file_name.toLowerCase().includes(searchQuery.toLowerCase());

    const statusMatch = statusFilter === "ALL" || sub.submission_status === statusFilter;

    return titleMatch && statusMatch;
  });

  return (
    <AppLayout
      requiredRole="STUDENT"
      breadcrumbs={[
        { label: "Dashboard", href: "/dashboard" },
        { label: "My Submissions & Feedback" },
      ]}
      actions={
        <Link
          href="/student/courses"
          className="text-xs font-semibold text-slate-300 hover:text-white py-1 px-3 rounded-lg bg-slate-800 border border-slate-700 transition-all flex items-center gap-1.5"
        >
          <span>📚</span>
          <span>Course Catalog</span>
        </Link>
      }
    >
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 border bg-indigo-500/10 text-indigo-400 border-indigo-500/30 font-mono">
            <span>📋</span> Student Deliverable Records
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            My Assignment Submissions &amp; Feedback
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            View your uploaded coursework, verification statuses, instructor marks &amp; feedback, and deliverable files.
          </p>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-3">
          <div className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] uppercase font-semibold text-slate-500 block">Total Submissions</span>
            <span className="text-lg font-bold text-white font-mono" id="total-submissions-count">
              {submissions.length}
            </span>
          </div>
          <div className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] uppercase font-semibold text-slate-500 block">Graded</span>
            <span className="text-lg font-bold text-purple-400 font-mono">
              {submissions.filter((s) => s.submission_status === "GRADED").length}
            </span>
          </div>
          <div className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] uppercase font-semibold text-slate-500 block">Pending</span>
            <span className="text-lg font-bold text-amber-400 font-mono">
              {submissions.filter((s) => s.submission_status !== "GRADED").length}
            </span>
          </div>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="mb-6 p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="w-full sm:w-72">
          <input
            id="submission-search-input"
            type="text"
            placeholder="Search assignment, course, or file..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-slate-400">Status:</span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
            {["ALL", "SUBMITTED", "LATE", "GRADED"].map((st) => (
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

      {/* Submissions Table */}
      {fetching ? (
        <LoadingSpinner message="Loading your submission history..." />
      ) : filteredSubmissions.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <div className="text-4xl mb-3">📁</div>
          <h2 className="text-lg font-bold text-white mb-1">No Submissions Found</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-4">
            {submissions.length === 0
              ? "You haven't submitted any assignment files yet. Go to your courses to submit assignments."
              : "No submissions match your current search or filter criteria."}
          </p>
          {submissions.length === 0 && (
            <Link
              href="/student/courses"
              className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition-all inline-block"
            >
              Browse Course Assignments
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-mono text-[10px]">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Assignment &amp; Course</th>
                  <th className="py-3.5 px-4 font-semibold">Deliverable File</th>
                  <th className="py-3.5 px-4 font-semibold">Status</th>
                  <th className="py-3.5 px-4 font-semibold">Grade &amp; Evaluation</th>
                  <th className="py-3.5 px-4 font-semibold">Submitted At</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {filteredSubmissions.map((s) => (
                  <tr key={s.submission_id} className="hover:bg-slate-800/40 transition-colors">
                    {/* Assignment & Course */}
                    <td className="py-4 px-4">
                      <div className="font-bold text-white text-sm">
                        {s.assignment_title || s.assignment_id}
                      </div>
                      <div className="text-slate-400 text-[11px] mt-0.5 flex items-center gap-1.5 font-mono">
                        <span className="text-indigo-400 font-semibold">{s.course_name || s.course_id}</span>
                        {s.assignment_deadline && (
                          <>
                            <span>•</span>
                            <span>Due: {new Date(s.assignment_deadline).toLocaleDateString()}</span>
                          </>
                        )}
                      </div>
                    </td>

                    {/* File Info */}
                    <td className="py-4 px-4 font-mono">
                      <div className="flex items-center gap-1.5 text-slate-200">
                        <span>📎</span>
                        <span className="truncate max-w-[140px] sm:max-w-xs">{s.file_name}</span>
                      </div>
                      {s.resubmission_count > 0 && (
                        <div className="mt-1">
                          <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[10px] font-bold">
                            v{s.resubmission_count + 1} (Resubmitted)
                          </span>
                        </div>
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-4 px-4">
                      <StatusBadge
                        status={s.submission_status}
                        resubmissionCount={s.resubmission_count}
                      />
                    </td>

                    {/* Grade & Feedback */}
                    <td className="py-4 px-4">
                      {s.submission_status === "GRADED" && s.marks !== null && s.marks !== undefined ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-emerald-400 font-bold text-xs font-mono">
                              {s.marks}{s.max_marks ? `/${s.max_marks}` : ""} pts
                            </span>
                            {s.graded_at && (
                              <span className="text-slate-500 text-[10px] font-mono">
                                ({new Date(s.graded_at).toLocaleDateString()})
                              </span>
                            )}
                          </div>
                          {s.feedback ? (
                            <p className="text-slate-300 text-[11px] italic bg-slate-950/40 p-1.5 rounded border border-slate-800/80 max-w-xs truncate">
                              &quot;{s.feedback}&quot;
                            </p>
                          ) : (
                            <span className="text-slate-500 text-[10px] italic">No written feedback</span>
                          )}
                        </div>
                      ) : s.resubmission_count > 0 ? (
                        <div className="text-[11px] text-indigo-300 flex items-center gap-1">
                          <span>🔄</span>
                          <span>Prior grade reset (Awaiting evaluation)</span>
                        </div>
                      ) : (
                        <span className="text-slate-500 text-[11px] flex items-center gap-1">
                          <span>⏳</span>
                          <span>Pending evaluation</span>
                        </span>
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
                          id={`view-submission-file-${s.submission_id}`}
                          className="py-1.5 px-3 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/40 transition-all flex items-center gap-1.5 disabled:opacity-50"
                        >
                          {downloadingId === s.submission_id ? (
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
