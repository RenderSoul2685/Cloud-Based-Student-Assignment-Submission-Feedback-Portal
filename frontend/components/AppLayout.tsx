"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import LoadingSpinner from "./LoadingSpinner";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface AppLayoutProps {
  children: React.ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
  requiredRole?: "STUDENT" | "TEACHER" | "ADMIN" | Array<"STUDENT" | "TEACHER" | "ADMIN">;
}

export default function AppLayout({
  children,
  breadcrumbs,
  actions,
  requiredRole,
}: AppLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, profile, loading, logout } = useAuth();

  // Auth & RBAC Route Guard
  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace("/login");
        return;
      }

      if (requiredRole && profile) {
        const allowedRoles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
        if (!allowedRoles.includes(profile.role)) {
          // If role not permitted, redirect to user dashboard
          router.replace("/dashboard");
        }
      }
    }
  }, [user, profile, loading, requiredRole, router]);

  if (loading || !user || !profile) {
    return <LoadingSpinner fullScreen message="Loading portal workspace..." />;
  }

  const role = profile.role;
  const isTeacherOrAdmin = role === "TEACHER" || role === "ADMIN";

  const navLinks = isTeacherOrAdmin
    ? [
        { label: "Dashboard", href: "/dashboard", icon: "📊" },
        { label: "My Courses", href: "/teacher/courses", icon: "📚" },
      ]
    : [
        { label: "Dashboard", href: "/dashboard", icon: "📊" },
        { label: "My Courses", href: "/student/courses", icon: "📚" },
        { label: "My Submissions", href: "/student/submissions", icon: "📋" },
      ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Brand Logo & Navigation */}
          <div className="flex items-center gap-6">
            <Link
              href="/dashboard"
              className="flex items-center gap-2.5 group"
              id="app-nav-brand-logo"
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white font-bold text-xs shadow-md shadow-indigo-600/30 group-hover:scale-105 transition-transform">
                CC
              </div>
              <div className="hidden sm:block">
                <span className="font-bold text-sm text-white tracking-tight block leading-tight">
                  Assignment Portal
                </span>
                <span className="text-[10px] text-indigo-400 font-mono">Cloud Serverless</span>
              </div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const isActive =
                  link.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(link.href);

                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                      isActive
                        ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-sm"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                    }`}
                  >
                    <span>{link.icon}</span>
                    <span>{link.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* User Menu & Role Badge */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2.5 px-3 py-1 rounded-xl bg-slate-900/90 border border-slate-800">
              <div className="text-right">
                <p className="text-xs font-semibold text-white leading-tight">{profile.name}</p>
                <p className="text-[10px] text-slate-400 font-mono truncate max-w-[140px]">
                  {profile.email}
                </p>
              </div>

              <span
                className={`px-2 py-0.5 rounded-md text-[9px] font-bold font-mono uppercase tracking-wider ${
                  role === "STUDENT"
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    : role === "TEACHER"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                }`}
              >
                {role}
              </span>
            </div>

            <button
              type="button"
              onClick={() => logout()}
              id="app-nav-logout-btn"
              className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-all flex items-center gap-1.5"
            >
              <span>Sign Out</span>
            </button>
          </div>
        </div>

        {/* Mobile Navigation Bar */}
        <div className="md:hidden border-t border-slate-800/60 bg-slate-950/80 px-4 py-2 flex items-center justify-around gap-1 overflow-x-auto">
          {navLinks.map((link) => {
            const isActive =
              link.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span>{link.icon}</span>
                <span>{link.label}</span>
              </Link>
            );
          })}
        </div>
      </header>

      {/* Subheader / Breadcrumbs bar if provided */}
      {(breadcrumbs || actions) && (
        <div className="border-b border-slate-800/60 bg-slate-900/30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 h-12 flex items-center justify-between gap-4">
            {breadcrumbs ? (
              <nav className="flex items-center gap-2 text-xs font-medium text-slate-400 overflow-x-auto">
                {breadcrumbs.map((b, idx) => (
                  <React.Fragment key={b.label + idx}>
                    {idx > 0 && <span className="text-slate-600">/</span>}
                    {b.href ? (
                      <Link
                        href={b.href}
                        className="hover:text-white transition-colors truncate max-w-[160px] sm:max-w-xs"
                      >
                        {b.label}
                      </Link>
                    ) : (
                      <span className="text-indigo-400 font-semibold truncate max-w-[180px] sm:max-w-sm">
                        {b.label}
                      </span>
                    )}
                  </React.Fragment>
                ))}
              </nav>
            ) : (
              <div />
            )}

            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        </div>
      )}

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {children}
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-slate-800/60 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Cloud-Based Student Assignment Submission &amp; Feedback Portal</span>
          <span className="font-mono text-[11px] text-slate-600">FastAPI • Next.js • Firebase Spark</span>
        </div>
      </footer>
    </div>
  );
}
