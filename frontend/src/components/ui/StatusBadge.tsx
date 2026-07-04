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
  Draft: "bg-slate-100 text-slate-600",
  Pending: "bg-amber-50 text-amber-700 border border-amber-200",
  Confirmed: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  Dispatched: "bg-blue-50 text-blue-700 border border-blue-200",
  Delivered: "bg-teal-50 text-teal-700 border border-teal-200",
  Cancelled: "bg-rose-50 text-rose-600 border border-rose-200",
  "Needs Review": "bg-orange-50 text-orange-700 border border-orange-200",
  PAID: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  UNPAID: "bg-rose-50 text-rose-600 border border-rose-200",
  PARTIALLY_PAID: "bg-amber-50 text-amber-700 border border-amber-200",
  "Low Stock": "bg-amber-50 text-amber-700 border border-amber-200",
  "Out of Stock": "bg-rose-50 text-rose-600 border border-rose-200",
  "In Stock": "bg-emerald-50 text-emerald-700 border border-emerald-200",
};

interface StatusBadgeProps {
  status: StatusVariant;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const styles = VARIANT_STYLES[status] || "bg-slate-100 text-slate-600";
  const sizeClass = size === "md" ? "px-3 py-1 text-xs" : "px-2.5 py-0.5 text-[11px]";
  return (
    <span className={`inline-flex items-center font-semibold rounded-full ${sizeClass} ${styles}`}>
      {status}
    </span>
  );
}
