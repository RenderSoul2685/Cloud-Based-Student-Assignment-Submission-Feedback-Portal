"use client";

import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";

export default function Home() {
  const { user, profile, loading } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Navigation Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white font-bold shadow-lg shadow-indigo-600/30">
              CC
            </div>
            <span className="font-bold text-base tracking-tight text-white">
              Cloud Assignment Portal
            </span>
          </div>

          <div className="flex items-center gap-3">
            {loading ? (
              <div className="text-xs text-slate-500">Checking auth...</div>
            ) : user ? (
              <Link
                href="/dashboard"
                className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
              >
                Go to Dashboard ({profile?.role || "User"})
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="py-2 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-4 py-20 relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute w-[500px] h-[500px] bg-indigo-600/10 rounded-full blur-3xl pointer-events-none top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"></div>

        <div className="relative z-10 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider mb-6 border bg-indigo-500/10 text-indigo-400 border-indigo-500/30">
            <span>🚀</span> Google Cloud & Firebase Spark Plan (Zero Cost)
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-tight">
            Cloud-Based Student Assignment &amp; Feedback Portal
          </h1>

          <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
            A cloud-native portal for coursework assignment submission, grading, and automated feedback with secure Firebase Authentication, Firestore document store, and role-based access control.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              id="hero-register-btn"
              className="w-full sm:w-auto py-3.5 px-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-xl shadow-indigo-600/30 hover:shadow-indigo-500/50 transition-all flex items-center justify-center gap-2"
            >
              <span>Create Account</span>
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M14 5l7 7m0 0l-7 7m7-7H3"
                />
              </svg>
            </Link>

            <Link
              href="/login"
              id="hero-login-btn"
              className="w-full sm:w-auto py-3.5 px-8 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white font-semibold border border-slate-700 backdrop-blur-sm transition-all"
            >
              Sign In with Existing Account
            </Link>
          </div>
        </div>

        {/* Feature Highlights Grid */}
        <div className="relative z-10 max-w-5xl mx-auto mt-20 grid grid-cols-1 sm:grid-cols-3 gap-6 text-left">
          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800/80 backdrop-blur-sm">
            <div className="text-2xl mb-3">🔐</div>
            <h3 className="font-bold text-white text-base mb-1">Role-Based Access</h3>
            <p className="text-xs text-slate-400">
              Strict separation between Student, Teacher, and Administrator roles enforced via JWT ID tokens on FastAPI backend.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800/80 backdrop-blur-sm">
            <div className="text-2xl mb-3">⚡</div>
            <h3 className="font-bold text-white text-base mb-1">Serverless Firestore</h3>
            <p className="text-xs text-slate-400">
              High-performance NoSQL document database indexing users, courses, assignments, and submission statuses.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800/80 backdrop-blur-sm">
            <div className="text-2xl mb-3">☁️</div>
            <h3 className="font-bold text-white text-base mb-1">Zero-Cost Cloud</h3>
            <p className="text-xs text-slate-400">
              Engineered exclusively within Google Cloud & Firebase Spark Free Tier limits for production-ready academic evaluation.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
        Cloud Computing Coursework &bull; Assignment Submission &amp; Feedback Portal
      </footer>
    </div>
  );
}
