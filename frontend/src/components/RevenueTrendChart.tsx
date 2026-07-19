"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import { LineChart, Loader2 } from "lucide-react";
import Link from "next/link";
import { fetchWithTimeout } from "@/lib/debounce";

interface TimeSeriesPoint {
  date: string;
  sales: number;
}

interface RevenueTrendData {
  total_revenue: number;
  total_receivables: number;
  time_series: TimeSeriesPoint[];
}

interface RevenueTrendChartProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(val);

/**
 * Compact revenue trend chart for the dashboard home page. Reuses the same
 * /api/v1/analytics/revenue-trend endpoint powering the full Reports page,
 * so the two views never disagree on numbers.
 */
export default function RevenueTrendChart({ activeTenantId }: RevenueTrendChartProps) {
  const [data, setData] = useState<RevenueTrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchTrend = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    setError(false);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/analytics/revenue-trend?tenant_id=${activeTenantId}`,
        { credentials: "include", timeout: 12000 }
      );
      if (!resp.ok) throw new Error("Failed to fetch revenue trend");
      const resData = await resp.json();
      setData(resData);
    } catch (err) {
      console.error("Revenue trend fetch failed:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchTrend();
  }, [fetchTrend]);

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
          <LineChart className="w-4 h-4 text-brand-blue" />
          <span>Revenue Trend</span>
        </h3>
        <Link
          href="/dashboard/reports"
          className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline"
        >
          Full report →
        </Link>
      </div>

      <div className="flex-1 w-full min-h-[220px]">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-xs font-semibold">Loading revenue trend...</span>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs font-semibold text-slate-400">
            Failed to load revenue trend.
          </div>
        ) : data && data.time_series.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.time_series} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorSalesDashboard" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} />
              <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(tick) => `₹${tick / 1000}k`} />
              <Tooltip
                contentStyle={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "8px",
                  color: "var(--color-text)"
                }}
                formatter={(value: any) => [formatCurrency(value), "Sales"]}
              />
              <Area type="monotone" dataKey="sales" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorSalesDashboard)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-xs font-semibold text-slate-400">
            No transactional sales data available yet.
          </div>
        )}
      </div>
    </div>
  );
}
