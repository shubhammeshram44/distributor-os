"use client";

import React, { useState, useEffect, useCallback } from "react";
import { TrendingUp, AlertTriangle, Wallet } from "lucide-react";

interface CashFlowForecast {
  expected_collections_this_week: number;
  at_risk: number;
  expected_customers_count: number;
  at_risk_customers_count: number;
}

interface CashFlowForecastCardProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);

export default function CashFlowForecastCard({ activeTenantId }: CashFlowForecastCardProps) {
  const [forecast, setForecast] = useState<CashFlowForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchForecast = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    setError(false);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(
        `${apiBase}/api/v1/dashboard/cash-flow-forecast?tenant_id=${activeTenantId}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("Non-200 response");
      const data: CashFlowForecast = await res.json();
      setForecast(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm h-full w-full flex flex-col">
      {/* Card header */}
      <div className="flex items-start justify-between pb-4 border-b border-dashboard-border mb-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0">
            <Wallet className="w-4 h-4" />
          </div>
          <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Cash Flow Forecast</h3>
        </div>
      </div>

      {/* Card body */}
      <div className="flex-1 flex flex-col justify-center gap-3">
        {loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="w-6 h-6 rounded-full border-4 border-slate-200 dark:border-white/10 border-t-emerald-400 animate-spin" />
            <span className="text-xs text-slate-400 font-semibold">Loading forecast...</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
            <AlertTriangle className="w-6 h-6 text-slate-300" />
            <span className="text-xs font-semibold">Failed to load cash flow forecast</span>
          </div>
        )}

        {!loading && !error && forecast && (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between px-3.5 py-3 rounded-lg border bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0 bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-emerald-700 dark:text-emerald-400 truncate">
                    Expected this week
                  </p>
                  <p className="text-[10px] text-slate-400 font-semibold">
                    {forecast.expected_customers_count} retailer
                    {forecast.expected_customers_count === 1 ? "" : "s"} on track
                  </p>
                </div>
              </div>
              <div className="text-right shrink-0 pl-2">
                <p className="text-sm font-extrabold text-emerald-700 dark:text-emerald-400">
                  {formatCurrency(forecast.expected_collections_this_week)}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between px-3.5 py-3 rounded-lg border bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0 bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-rose-700 dark:text-rose-400 truncate">
                    At risk
                  </p>
                  <p className="text-[10px] text-slate-400 font-semibold">
                    {forecast.at_risk_customers_count} retailer
                    {forecast.at_risk_customers_count === 1 ? "" : "s"} overdue
                  </p>
                </div>
              </div>
              <div className="text-right shrink-0 pl-2">
                <p className="text-sm font-extrabold text-rose-700 dark:text-rose-400">
                  {formatCurrency(forecast.at_risk)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
