"use client";

import React from "react";

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = "", style }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-slate-200 dark:bg-white/[0.06] ${className}`}
      style={style}
      aria-hidden="true"
    />
  );
}

export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="border-b border-dashboard-border">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-7 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} cols={cols} />
      ))}
    </tbody>
  );
}

/** Placeholder for a chart-bearing card (analytics/reports), mimics the real
 * card's title bar + a fake bar-chart silhouette so the layout doesn't jump
 * once real data/Recharts renders in. */
export function SkeletonChartCard({ height = "h-[400px]" }: { height?: string }) {
  const bars = [55, 80, 40, 95, 65, 45, 75];
  return (
    <div className={`bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm flex flex-col ${height}`}>
      <Skeleton className="h-4 w-1/3 mb-6" />
      <div className="flex-1 flex items-end justify-between gap-3 px-2">
        {bars.map((h, i) => (
          <Skeleton key={i} className="w-full rounded-t-md rounded-b-none" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

/** Placeholder for a conversation/contact list row (avatar + two text lines),
 * used by inbox-style panels (Messages) while the list is being fetched. */
export function SkeletonListItem() {
  return (
    <div className="w-full p-4 flex gap-3 border-l-4 border-transparent">
      <Skeleton className="w-10 h-10 rounded-full shrink-0" />
      <div className="min-w-0 flex-1 space-y-2 py-0.5">
        <div className="flex items-center justify-between gap-2">
          <Skeleton className="h-3 w-1/3" />
          <Skeleton className="h-2.5 w-10" />
        </div>
        <Skeleton className="h-2.5 w-2/3" />
      </div>
    </div>
  );
}
