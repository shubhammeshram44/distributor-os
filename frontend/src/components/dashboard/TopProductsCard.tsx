"use client";

import React from "react";
import { TrendingUp } from "lucide-react";
import type { TopMovingSku } from "@/hooks/useSalesOverview";

interface TopProductsCardProps {
  products: TopMovingSku[];
  isLoading: boolean;
}

const formatCurrency = (value: number) =>
  `₹${value >= 100000 ? `${(value / 100000).toFixed(1)}L` : value.toLocaleString("en-IN")}`;

/** Top 5 SKUs by quantity sold, sourced from /api/v1/analytics/sales-overview. */
export default function TopProductsCard({ products, isLoading }: TopProductsCardProps) {
  const top5 = products.slice(0, 5);
  const maxQty = Math.max(...top5.map((p) => p.total_quantity), 1);

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-dashDark-text text-sm">Top Products (MTD)</h3>
        <TrendingUp className="w-4 h-4 text-emerald-400" />
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse flex-1">
          {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-dashDark-cardAlt rounded-lg" />)}
        </div>
      ) : top5.length === 0 ? (
        <p className="text-xs text-dashDark-textMuted flex-1 flex items-center justify-center">No sales data yet this period</p>
      ) : (
        <div className="space-y-3 flex-1">
          {top5.map((product, i) => (
            <div key={product.sku_code}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] font-bold text-dashDark-textFaint w-3">{i + 1}</span>
                  <span className="text-xs font-semibold text-dashDark-text truncate">{product.brand} {product.sku_code}</span>
                </div>
                <span className="text-[11px] font-bold text-dashDark-textMuted shrink-0 ml-2">
                  {formatCurrency(product.total_revenue)}
                </span>
              </div>
              <div className="h-1.5 bg-dashDark-cardAlt rounded-full overflow-hidden ml-5">
                <div
                  className="h-full rounded-full bg-brand-blue"
                  style={{ width: `${(product.total_quantity / maxQty) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
