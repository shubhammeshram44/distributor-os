"use client";

import React, { useEffect, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

export type ToastType = "success" | "error" | "info";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

function ToastItem({ toast, onRemove }: ToastItemProps) {
  useEffect(() => {
    const timer = setTimeout(() => onRemove(toast.id), 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  const styles = {
    success: "bg-white dark:bg-dashboard-card border-success-500 text-success-700",
    error: "bg-white dark:bg-dashboard-card border-danger-500 text-danger-700",
    info: "bg-white dark:bg-dashboard-card border-brand-blue text-brand-blue",
  };

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-success-600 flex-shrink-0" />,
    error: <AlertCircle className="w-4 h-4 text-danger-600 flex-shrink-0" />,
    info: <Info className="w-4 h-4 text-brand-blue flex-shrink-0" />,
  };

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg min-w-[280px] max-w-sm animate-slide-in ${styles[toast.type]}`}
      role="alert"
      aria-live="polite"
    >
      {icons[toast.type]}
      <span className="text-sm font-semibold flex-1 text-slate-700 dark:text-slate-300">{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors ml-1"
        aria-label="Dismiss notification"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed bottom-6 right-6 flex flex-col gap-2 z-[9999]"
      aria-label="Notifications"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={onRemove} />
      ))}
    </div>
  );
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "info") => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = {
    success: (msg: string) => addToast(msg, "success"),
    error: (msg: string) => addToast(msg, "error"),
    info: (msg: string) => addToast(msg, "info"),
  };

  return { toasts, toast, removeToast };
}
