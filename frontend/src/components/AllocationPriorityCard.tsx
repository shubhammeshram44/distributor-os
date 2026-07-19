"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Users, ChevronDown, ChevronUp } from "lucide-react";
import { fetchWithTimeout } from "@/lib/debounce";

interface ScoreBreakdown {
  payment_consistency: number;
  orders_last_30_days: number;
  orders_last_90_days: number;
  order_frequency_score: number;
  revenue_last_90_days: number;
  relationship_value_score: number;
}

interface RankedCustomer {
  customer_id: string;
  customer_name: string;
  score: number;
  open_gap_qty: number;
  open_gap_revenue_at_risk: number;
  score_breakdown: ScoreBreakdown;
}

interface AllocationPriorityCardProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

/**
 * Read-only preview of which customers should be prioritized when stock is
 * limited across multiple open demand gaps — ranked by a composite score
 * (payment consistency, order frequency, relationship value). Not wired into
 * any allocation action; this is advisory only. See
 * app/services/customer_scoring_service.py for the scoring methodology.
 */
export default function AllocationPriorityCard({ activeTenantId }: AllocationPriorityCardProps) {
  const [items, setItems] = useState<RankedCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchRanking = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/dashboard/allocation-priority?tenant_id=${activeTenantId}`,
        { credentials: "include", timeout: 12000 }
      );
      if (resp.ok) {
        const data = await resp.json();
        setItems(data.items ?? []);
      }
    } catch (err) {
      console.error("Failed to load allocation priority ranking:", err);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, apiBase]);

  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  if (!loading && items.length === 0) return null;

  return (
    <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center shrink-0">
            <Users className="w-4 h-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Allocation Priority (Preview)</h3>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              {loading ? "Ranking customers..." : `${items.length} customer${items.length === 1 ? "" : "s"} waiting on limited stock`}
            </p>
          </div>
        </div>
        {collapsed ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronUp className="w-4 h-4 text-slate-400" />}
      </button>

      {!collapsed && !loading && (
        <div className="divide-y divide-slate-50 dark:divide-white/5 border-t border-slate-100 dark:border-white/5">
          {items.map((item, idx) => (
            <div key={item.customer_id}>
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === item.customer_id ? null : item.customer_id)}
                className="w-full flex items-center gap-4 px-5 py-3 text-left hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
              >
                <span className="w-6 h-6 rounded-full bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 text-[11px] font-bold flex items-center justify-center shrink-0">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">{item.customer_name}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Short {item.open_gap_qty} units · {formatCurrency(item.open_gap_revenue_at_risk)} at risk</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-extrabold text-violet-600 dark:text-violet-400">{item.score}</p>
                  <p className="text-[10px] text-slate-400">score</p>
                </div>
              </button>
              {expandedId === item.customer_id && (
                <div className="px-5 pb-3 -mt-1 grid grid-cols-3 gap-2 text-[11px]">
                  <div className="rounded-lg bg-slate-50 dark:bg-dashboard-inset p-2">
                    <p className="font-semibold text-slate-500 dark:text-slate-400">Payment consistency</p>
                    <p className="font-bold text-slate-700 dark:text-slate-200">{item.score_breakdown.payment_consistency}%</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 dark:bg-dashboard-inset p-2">
                    <p className="font-semibold text-slate-500 dark:text-slate-400">Orders (90d)</p>
                    <p className="font-bold text-slate-700 dark:text-slate-200">{item.score_breakdown.orders_last_90_days}</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 dark:bg-dashboard-inset p-2">
                    <p className="font-semibold text-slate-500 dark:text-slate-400">Revenue (90d)</p>
                    <p className="font-bold text-slate-700 dark:text-slate-200">{formatCurrency(item.score_breakdown.revenue_last_90_days)}</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
