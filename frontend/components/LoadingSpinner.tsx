import React from "react";

interface LoadingSpinnerProps {
  message?: string;
  fullScreen?: boolean;
  size?: "sm" | "md" | "lg";
}

export default function LoadingSpinner({
  message = "Loading...",
  fullScreen = false,
  size = "md",
}: LoadingSpinnerProps) {
  const sizeClasses =
    size === "sm"
      ? "h-5 w-5 border-2"
      : size === "lg"
      ? "h-12 w-12 border-3"
      : "h-8 w-8 border-2";

  const content = (
    <div className="flex flex-col items-center justify-center gap-3 py-6 px-4">
      <div
        className={`animate-spin rounded-full border-t-transparent border-indigo-500 ${sizeClasses}`}
        role="status"
        aria-label="loading"
      />
      {message && <p className="text-xs sm:text-sm font-medium text-slate-400">{message}</p>}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        {content}
      </div>
    );
  }

  return content;
}
