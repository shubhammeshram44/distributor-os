"use client";

import React from "react";
import { AlertCircle, X } from "lucide-react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  isDestructive?: boolean;
  isLoading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}

export default function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  isDestructive = false,
  isLoading = false,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  const handleConfirm = async () => {
    await onConfirm();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 p-6 animate-scale-in">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              isDestructive ? "bg-rose-100" : "bg-amber-100"
            }`}>
              <AlertCircle className={`w-6 h-6 ${isDestructive ? "text-rose-600" : "text-amber-600"}`} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800">{title}</h3>
              <p className="text-sm text-slate-500 mt-1">{description}</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex gap-3 justify-end mt-6">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-semibold text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className={`px-4 py-2 text-sm font-semibold text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2 ${
              isDestructive
                ? "bg-rose-600 hover:bg-rose-700"
                : "bg-brand-blue hover:bg-brand-blueHover"
            }`}
          >
            {isLoading && (
              <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
