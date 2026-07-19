"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Trophy, AlertTriangle, Package } from "lucide-react";

interface SKUData {
  sku_code: string;
  brand: string;
  category: string;
  pack_size?: string;
  total_quantity: number;
  total_revenue?: number;
}

interface TopProductsCardProps {
  activeTenantId: string;
}

const formatCurrency = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);

const RANK_BADGE = [
  "bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400",
  "bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-slate-300",
  "bg-orange-100 dark:bg-orange-500/15 text-orange-700 dark:text-orange-400",
  "bg-slate-50 dark:bg-white/5 text-slate-500 dark:text-slate-400",
  "bg-slate-50 dark:bg-white/5 text-slate-500 dark:text-slate-400",
];

export default function TopProductsCard({ activeTenantId }: TopProductsCardProps) {
  const [skus, setSkus] = useState<SKUData[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchTopProducts = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    setError(false);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(
        `${apiBase}/api/v1/analytics/sales-overview?tenant_id=${activeTenantId}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("Non-200 response");
      const data = await res.json();
      setSkus(data.top_moving_skus || []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchTopProducts();
  }, [fetchTopProducts]);

  const maxQuantity = skus && skus.length > 0 ? Math.max(...skus.map((s) => s.total_quantity)) : 0;

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm h-full w-full flex flex-col">
      {/* Card header */}
      <div className="flex items-start justify-between pb-4 border-b border-dashboard-border mb-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0">
            <Trophy className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Top Products</h3>
            <p className="text-[10px] text-slate-400 font-semibold">Best sellers by units moved</p>
          </div>
        </div>
        <a
          href="/dashboard/sales-analytics"
          className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline shrink-0"
        >
          View all →
        </a>
      </div>

      {/* Card body */}
      <div className="flex-1 flex flex-col justify-start gap-2.5">
        {loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="w-6 h-6 rounded-full border-4 border-slate-200 dark:border-white/10 border-t-emerald-400 animate-spin" />
            <span className="text-xs text-slate-400 font-semibold">Loading top products...</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
            <AlertTriangle className="w-6 h-6 text-slate-300" />
            <span className="text-xs font-semibold">Failed to load top products</span>
          </div>
        )}

        {!loading && !error && skus && skus.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
            <Package className="w-6 h-6 text-slate-300" />
            <span className="text-xs font-semibold">No sales recorded yet</span>
          </div>
        )}

        {!loading && !error && skus && skus.length > 0 && (
          <div className="space-y-2">
            {skus.map((sku, idx) => (
              <div
                key={sku.sku_code}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-slate-100 dark:border-white/[0.08] bg-slate-50/60 dark:bg-dashboard-inset"
              >
                <div
                  className={`w-6 h-6 rounded-md flex items-center justify-center text-[11px] font-extrabold shrink-0 ${RANK_BADGE[idx % RANK_BADGE.length]
                    }`}
                >
                  {idx + 1}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-slate-800 dark:text-slate-100 truncate">
                    {sku.brand} · {sku.sku_code}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 bg-slate-200 dark:bg-white/10 rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-emerald-400"
                        style={{
                          width: `${maxQuantity > 0 ? (sku.total_quantity / maxQuantity) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 font-semibold shrink-0">
                      {sku.total_quantity} units
                    </span>
                  </div>
                </div>

                {typeof sku.total_revenue === "number" && (
                  <div className="text-right shrink-0 pl-1">
                    <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300">
                      {formatCurrency(sku.total_revenue)}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
