import React from "react";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-3xl flex items-center justify-center mx-auto shadow-xl shadow-indigo-950/40">
          🔍
        </div>

        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 font-mono">
            404 Error • Resource Not Found
          </span>
          <h1 className="text-3xl font-bold text-white tracking-tight mt-1">Page Not Found</h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-2 leading-relaxed">
            The page or assignment you requested does not exist, was removed, or you might not have permission to view it.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard"
            className="w-full sm:w-auto py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2"
          >
            <span>📊 Return to Dashboard</span>
          </Link>
          <Link
            href="/"
            className="w-full sm:w-auto py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-xl border border-slate-700 transition-all flex items-center justify-center"
          >
            Home Page
          </Link>
        </div>
      </div>
    </div>
  );
}
