import React from 'react';
import { useDashboardData } from '@/hooks/useDashboardData';

// Reusable, structurally isolated Empty State component
const DashboardEmptyState = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[350px] w-full rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center transition-all dark:border-slate-800 dark:bg-slate-900/20">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
        <svg 
          className="h-6 w-6 text-slate-400" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor" 
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
        </svg>
      </div>
      <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-slate-100">No Operational Data Syncing</h3>
      <p className="mt-2 text-xs max-w-sm text-slate-500 dark:text-slate-400">
        Your workspace is connected perfectly! Once your Tally/Marg instance forwards WhatsApp orders, live analytic metrics will fill this workspace.
      </p>
    </div>
  );
};

export default function DashboardMetricsGrid() {
  const { data, isLoading, error } = useDashboardData();

  // 1. Keep layout stable during skeleton loading phase
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 w-full animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 w-full rounded-xl bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
    );
  }

  // 2. Explicitly catch zero or empty operational states cleanly 
  const hasNoData = !data || data.ordersCount === 0 || data.lineItems?.length === 0;

  if (hasNoData || error) {
    return (
      <div className="w-full p-1">
        <DashboardEmptyState />
      </div>
    );
  }

  // 3. Render real UI panels safely knowing data exists
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 w-full">
      <div className="p-6 rounded-xl border border-slate-100 bg-white shadow-sm">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Orders</p>
        <h3 className="text-2xl font-bold tracking-tight mt-1 text-slate-900">{data.ordersCount}</h3>
      </div>
      {/* Additional populated metric cards go here */}
    </div>
  );
}
