import React from "react";

export type SubmissionStatusType =
  | "SUBMITTED"
  | "LATE"
  | "GRADED"
  | "NOT_SUBMITTED"
  | string;

interface StatusBadgeProps {
  status: SubmissionStatusType;
  resubmissionCount?: number;
  className?: string;
  size?: "sm" | "md";
}

export default function StatusBadge({
  status,
  resubmissionCount = 0,
  className = "",
  size = "md",
}: StatusBadgeProps) {
  const normStatus = String(status).toUpperCase();

  let colorClasses = "bg-slate-800 text-slate-400 border-slate-700";
  let label = normStatus;

  if (normStatus === "SUBMITTED") {
    colorClasses = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    label = "Submitted";
  } else if (normStatus === "LATE") {
    colorClasses = "bg-amber-500/20 text-amber-300 border-amber-500/40";
    label = "Late";
  } else if (normStatus === "GRADED") {
    colorClasses = "bg-purple-500/20 text-purple-300 border-purple-500/40";
    label = "Graded";
  } else if (normStatus === "NOT_SUBMITTED") {
    colorClasses = "bg-slate-800 text-slate-400 border-slate-700";
    label = "Not Submitted";
  }

  const paddingClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[9px]"
      : "px-2.5 py-0.5 text-[10px]";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-bold uppercase tracking-wider border font-mono ${paddingClasses} ${colorClasses} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      <span>{label}</span>
      {resubmissionCount > 0 && normStatus !== "NOT_SUBMITTED" && (
        <span className="opacity-80 font-normal">
          (v{resubmissionCount + 1})
        </span>
      )}
    </span>
  );
}
