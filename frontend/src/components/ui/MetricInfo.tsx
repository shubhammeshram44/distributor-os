"use client";

import React from "react";
import { Info } from "lucide-react";

/**
 * Small ⓘ control for dashboard metrics.
 * Uses native title + hover tooltip. No behaviour change to parent metrics.
 */
export default function MetricInfo({ text }: { text: string }) {
  return (
    <span className="relative inline-flex items-center group/metric-info ml-1 align-middle">
      <button
        type="button"
        className="inline-flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40"
        aria-label={text}
        title={text}
      >
        <Info className="w-3.5 h-3.5" strokeWidth={2} />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-20 mt-1.5 w-52 -translate-x-1/2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-medium leading-snug text-slate-600 opacity-0 shadow-md transition-opacity duration-150 group-hover/metric-info:opacity-100 group-focus-within/metric-info:opacity-100 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
      >
        {text}
      </span>
    </span>
  );
}
