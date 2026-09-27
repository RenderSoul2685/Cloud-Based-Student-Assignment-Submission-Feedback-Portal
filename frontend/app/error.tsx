"use client";

import React, { useEffect } from "react";
import Link from "next/link";

export default function GlobalErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled client exception:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full text-center space-y-6 bg-slate-900/80 border border-slate-800 p-8 rounded-2xl shadow-2xl backdrop-blur-md">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-3xl flex items-center justify-center mx-auto shadow-xl shadow-rose-950/40">
          ⚠️
        </div>

        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-rose-400 font-mono">
            Application Error
          </span>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Something went wrong</h1>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            An unexpected error occurred while rendering this view.
          </p>
          {error?.message && (
            <div className="mt-3 p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-rose-300 break-words text-left max-h-28 overflow-y-auto">
              {error.message}
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="w-full sm:w-auto py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2"
          >
            <span>🔄 Try Again</span>
          </button>
          <Link
            href="/dashboard"
            className="w-full sm:w-auto py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-xl border border-slate-700 transition-all flex items-center justify-center"
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
