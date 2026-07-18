"use client";

import React, { useState, useEffect, useCallback } from "react";
import { TrendingDown, AlertTriangle, CreditCard, Package } from "lucide-react";

/**
 * Maps a reason_code string to a colour palette token and an icon component.
 * New reason codes added on the backend will fall through to the default (slate/TrendingDown).
 */
function reasonStyle(reasonCode: string): {
  bg: string;
  text: string;
  border: string;
  badge: string;
  Icon: React.ElementType;
} {
  switch (reasonCode) {
    case "STOCK_SHORTAGE":
      return {
        bg: "bg-amber-50 dark:bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        border: "border-amber-200 dark:border-amber-500/20",
        badge: "bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400",
        Icon: Package,
      };
    case "CREDIT_LIMIT":
      return {
        bg: "bg-rose-50 dark:bg-rose-500/10",
        text: "text-rose-700 dark:text-rose-400",
        border: "border-rose-200 dark:border-rose-500/20",
        badge: "bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-400",
        Icon: CreditCard,
      };
    default:
      return {
        bg: "bg-slate-50 dark:bg-dashboard-inset",
        text: "text-slate-700 dark:text-slate-300",
        border: "border-slate-200 dark:border-white/10",
        badge: "bg-slate-100 dark:bg-white/5 text-slate-700 dark:text-slate-300",
        Icon: TrendingDown,
      };
  }
}

/** Human-readable label for a reason code. Falls back to the raw code. */
function reasonLabel(reasonCode: string): string {
  const labels: Record<string, string> = {
    STOCK_SHORTAGE: "Stock Shortages",
    CREDIT_LIMIT: "Credit Limit Blocks",
  };
  return labels[reasonCode] ?? reasonCode;
}

interface ByReasonEntry {
  reason_code: string;
  events: number;
  units_gap: number | null;
  revenue_at_risk: number;
  customers_affected: number;
}

interface DemandGapSummary {
  window_days: number;
  total_revenue_at_risk: number;
  distinct_customers_affected: number;
  by_reason: ByReasonEntry[];
}

interface DemandGapCardProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);

export default function DemandGapCard({ activeTenantId }: DemandGapCardProps) {
  const [summary, setSummary] = useState<DemandGapSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Default window: 7 days (matches API default)
  const DAYS = 7;

  const fetchSummary = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    setError(false);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(
        `${apiBase}/api/v1/dashboard/demand-gap-summary?tenant_id=${activeTenantId}&days=${DAYS}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("Non-200 response");
      const data: DemandGapSummary = await res.json();
      setSummary(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  /** Compose the headline sentence from live API data — never hardcodes any numbers. */
  const headline = (): React.ReactNode => {
    if (!summary) return null;

    const { window_days, total_revenue_at_risk, distinct_customers_affected } = summary;

    if (total_revenue_at_risk === 0) {
      return (
        <p className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold mt-1">
          No demand gaps recorded in the last{" "}
          <span className="font-bold">{window_days}</span>{" "}
          {window_days === 1 ? "day" : "days"} ✓
        </p>
      );
    }

    return (
      <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold mt-1 leading-relaxed">
        In the last{" "}
        <span className="font-bold text-slate-700 dark:text-slate-300">{window_days}</span>{" "}
        {window_days === 1 ? "day" : "days"} you lost{" "}
        <span className="font-bold text-rose-600 dark:text-rose-400">
          {formatCurrency(total_revenue_at_risk)}
        </span>{" "}
        —{" "}
        <span className="font-bold text-slate-700 dark:text-slate-300">
          {distinct_customers_affected}
        </span>{" "}
        retailer{distinct_customers_affected === 1 ? "" : "s"} affected.
      </p>
    );
  };

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm h-full w-full flex flex-col">
      {/* Card header */}
      <div className="flex items-start justify-between pb-4 border-b border-dashboard-border mb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center text-rose-500 shrink-0">
              <TrendingDown className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Demand Gap</h3>
          </div>
          {!loading && !error && headline()}
        </div>
      </div>

      {/* Card body */}
      <div className="flex-1 flex flex-col justify-start gap-3">
        {loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="w-6 h-6 rounded-full border-4 border-slate-200 dark:border-white/10 border-t-rose-400 animate-spin" />
            <span className="text-xs text-slate-400 font-semibold">Loading gap data...</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
            <AlertTriangle className="w-6 h-6 text-slate-300" />
            <span className="text-xs font-semibold">Failed to load demand gap data</span>
          </div>
        )}

        {!loading && !error && summary && summary.by_reason.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
            <TrendingDown className="w-6 h-6 text-emerald-300" />
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              All demand fulfilled in this window
            </span>
          </div>
        )}

        {/* Generic reason breakdown — renders whatever the API returns */}
        {!loading && !error && summary && summary.by_reason.length > 0 && (
          <div className="space-y-2.5">
            {summary.by_reason.map((entry) => {
              const style = reasonStyle(entry.reason_code);
              const { Icon } = style;
              return (
                <div
                  key={entry.reason_code}
                  className={`flex items-center justify-between px-3.5 py-3 rounded-lg border ${style.bg} ${style.border}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${style.badge}`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <p className={`text-xs font-bold ${style.text} truncate`}>
                        {reasonLabel(entry.reason_code)}
                      </p>
                      <p className="text-[10px] text-slate-400 font-semibold">
                        {entry.events} event{entry.events === 1 ? "" : "s"}
                        {entry.units_gap !== null
                          ? ` · ${entry.units_gap} unit${entry.units_gap === 1 ? "" : "s"} short`
                          : ""}
                        {" · "}
                        {entry.customers_affected} retailer
                        {entry.customers_affected === 1 ? "" : "s"}
                      </p>
                    </div>
                  </div>
                  <div className="text-right shrink-0 pl-2">
                    <p className={`text-sm font-extrabold ${style.text}`}>
                      {formatCurrency(entry.revenue_at_risk)}
                    </p>
                    <p className="text-[10px] text-slate-400 font-semibold">at risk</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
