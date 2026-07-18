"use client";

import React from "react";

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

export function CardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm h-32 animate-pulse" />
      ))}
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm">
      <div className="h-6 bg-slate-100 rounded w-32 mb-4 animate-pulse" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-4 bg-slate-100 rounded flex-1 animate-pulse" />
            <div className="h-4 bg-slate-100 rounded w-12 animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <div className="h-4 bg-slate-100 rounded w-24 animate-pulse" />
          <div className="h-10 bg-slate-100 rounded animate-pulse" />
        </div>
      ))}
    </div>
  );
}

export function ListSkeleton({ items = 8 }: { items?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="h-16 bg-slate-50 rounded-lg border border-dashboard-border animate-pulse" />
      ))}
    </div>
  );
}
