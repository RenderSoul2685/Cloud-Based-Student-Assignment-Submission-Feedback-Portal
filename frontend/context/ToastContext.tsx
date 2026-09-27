"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, message, type }]);

      // Auto dismiss after 4.5 seconds
      setTimeout(() => {
        removeToast(id);
      }, 4500);
    },
    [removeToast]
  );

  const success = useCallback((message: string) => showToast(message, "success"), [showToast]);
  const error = useCallback((message: string) => showToast(message, "error"), [showToast]);
  const info = useCallback((message: string) => showToast(message, "info"), [showToast]);
  const warning = useCallback((message: string) => showToast(message, "warning"), [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning, removeToast }}>
      {children}
      {/* Fixed Toast Container */}
      <div
        aria-live="polite"
        id="toast-container"
        className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        {toasts.map((t) => {
          const bgBorder =
            t.type === "success"
              ? "bg-slate-900/95 border-emerald-500/40 text-emerald-300 shadow-emerald-950/40"
              : t.type === "error"
              ? "bg-slate-900/95 border-rose-500/40 text-rose-300 shadow-rose-950/40"
              : t.type === "warning"
              ? "bg-slate-900/95 border-amber-500/40 text-amber-300 shadow-amber-950/40"
              : "bg-slate-900/95 border-indigo-500/40 text-indigo-300 shadow-indigo-950/40";

          const icon =
            t.type === "success" ? "✅" : t.type === "error" ? "❌" : t.type === "warning" ? "⚠️" : "ℹ️";

          return (
            <div
              key={t.id}
              role="status"
              className={`pointer-events-auto p-3.5 rounded-xl border backdrop-blur-md shadow-xl flex items-start justify-between gap-3 text-xs transition-all animate-in slide-in-from-bottom-3 duration-200 ${bgBorder}`}
            >
              <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <span className="text-sm flex-shrink-0">{icon}</span>
                <p className="text-slate-100 font-medium leading-relaxed break-words">{t.message}</p>
              </div>
              <button
                type="button"
                onClick={() => removeToast(t.id)}
                className="text-slate-400 hover:text-white transition-colors flex-shrink-0 text-sm p-0.5"
                aria-label="Dismiss notification"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
