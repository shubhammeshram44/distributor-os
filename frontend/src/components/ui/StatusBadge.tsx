"use client";

import React from "react";

type StatusVariant =
  | "Draft"
  | "Pending"
  | "Confirmed"
  | "Dispatched"
  | "Delivered"
  | "Cancelled"
  | "Needs Review"
  | "PAID"
  | "UNPAID"
  | "PARTIALLY_PAID"
  | "Low Stock"
  | "Out of Stock"
  | "In Stock"
  | string;

const VARIANT_STYLES: Record<string, string> = {
  Draft: "bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400",
  Pending: "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20",
  Confirmed: "bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20",
  Dispatched: "bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20",
  Delivered: "bg-teal-50 text-teal-700 border border-teal-200 dark:bg-teal-500/10 dark:text-teal-400 dark:border-teal-500/20",
  Cancelled: "bg-rose-50 text-rose-600 border border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/20",
  "Needs Review": "bg-orange-50 text-orange-700 border border-orange-200 dark:bg-orange-500/10 dark:text-orange-400 dark:border-orange-500/20",
  PAID: "bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20",
  UNPAID: "bg-rose-50 text-rose-600 border border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/20",
  PARTIALLY_PAID: "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20",
  "Low Stock": "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20",
  "Out of Stock": "bg-rose-50 text-rose-600 border border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/20",
  "In Stock": "bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20",
};

interface StatusBadgeProps {
  status: StatusVariant;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const styles = VARIANT_STYLES[status] || "bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400";
  const sizeClass = size === "md" ? "px-3 py-1 text-xs" : "px-2.5 py-0.5 text-[11px]";
  return (
    <span className={`inline-flex items-center font-semibold rounded-full ${sizeClass} ${styles}`}>
      {status}
    </span>
  );
}
