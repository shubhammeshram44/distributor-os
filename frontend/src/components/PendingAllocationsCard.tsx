"use client";

import React, { useState, useEffect, useCallback } from "react";
import { PackageCheck, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { fetchWithTimeout } from "@/lib/debounce";

interface PendingAllocation {
  demand_gap_id: string;
  order_id: string | null;
  internal_order_id: string | null;
  customer_name: string;
  sku_id: string | null;
  brand: string | null;
  requested_qty: number | null;
  allocated_qty: number | null;
  gap_qty: number | null;
  available_now: number;
  can_fulfil_now: boolean;
  revenue_at_risk: number;
}

interface PendingAllocationsCardProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(val);

/**
 * "Stock Arrived — Review Allocations" queue. Lists open stock-shortage
 * demand gaps (oldest first) so a distributor can approve fulfilling them
 * once inventory is replenished, instead of the shortfall sitting silently
 * forever. Self-contained: own fetch, own loading/error state.
 */
export default function PendingAllocationsCard({ activeTenantId }: PendingAllocationsCardProps) {
  const [items, setItems] = useState<PendingAllocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchQueue = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/orders/pending-allocations?tenant_id=${activeTenantId}`,
        { credentials: "include", timeout: 12000 }
      );
      if (resp.ok) {
        const data = await resp.json();
        setItems(data.items ?? []);
      }
    } catch (err) {
      console.error("Failed to load pending allocations:", err);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, apiBase]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleApprove = async (demandGapId: string) => {
    setApprovingId(demandGapId);
    try {
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/orders/pending-allocations/${demandGapId}/approve?tenant_id=${activeTenantId}`,
        { method: "POST", credentials: "include", timeout: 10000 }
      );
      if (resp.ok) {
        await fetchQueue();
      }
    } catch (err) {
      console.error("Failed to approve allocation:", err);
    } finally {
      setApprovingId(null);
    }
  };

  // Don't render anything while loading on first mount, or once the queue is empty.
  if (!loading && items.length === 0) return null;

  return (
    <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
            <PackageCheck className="w-4 h-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Stock Arrived — Review Allocations</h3>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              {loading ? "Checking for pending allocations..." : `${items.length} order${items.length === 1 ? "" : "s"} waiting on stock`}
            </p>
          </div>
        </div>
        {collapsed ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronUp className="w-4 h-4 text-slate-400" />}
      </button>

      {!collapsed && !loading && (
        <div className="divide-y divide-slate-50 dark:divide-white/5 border-t border-slate-100 dark:border-white/5">
          {items.map((item) => (
            <div key={item.demand_gap_id} className="flex items-center gap-4 px-5 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                  {item.internal_order_id || "Order"} · {item.customer_name}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {item.brand || item.sku_id} — short {item.gap_qty} of {item.requested_qty} units
                  {item.can_fulfil_now ? ` · ${item.available_now} now in stock` : " · still out of stock"}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs font-bold text-rose-600 dark:text-rose-400">{formatCurrency(item.revenue_at_risk)}</p>
                <p className="text-[10px] text-slate-400">at risk</p>
              </div>
              <button
                type="button"
                disabled={!item.can_fulfil_now || approvingId === item.demand_gap_id}
                onClick={() => handleApprove(item.demand_gap_id)}
                className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
              >
                {approvingId === item.demand_gap_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                Approve
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
