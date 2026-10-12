"use client";

import React from "react";
import { AlertCircle, Layers, DollarSign, ArrowRight } from "lucide-react";
import Link from "next/link";

interface InventorySummaryProps {
  data?: {
    total_skus?: number;
    low_stock_count?: number;
    out_of_stock_count?: number;
    total_inventory_value?: number;
  };
}

export default function InventorySummary({ data }: InventorySummaryProps) {
  const totalSkus = data?.total_skus ?? 0;
  const lowStockCount = data?.low_stock_count ?? 0;
  const outOfStockCount = data?.out_of_stock_count ?? 0;
  const healthyCount = Math.max(0, totalSkus - lowStockCount - outOfStockCount);
  const healthPct = totalSkus > 0 ? Math.round((healthyCount / totalSkus) * 100) : 0;

  const healthBand =
    totalSkus === 0
      ? { label: "No data", color: "text-slate-400", bar: "bg-slate-300" }
      : healthPct >= 80
      ? { label: "Healthy", color: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" }
      : healthPct >= 50
      ? { label: "Needs attention", color: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" }
      : { label: "At risk", color: "text-rose-600 dark:text-rose-400", bar: "bg-rose-500" };

  const healthyPct = totalSkus > 0 ? (healthyCount / totalSkus) * 100 : 0;
  const lowPct = totalSkus > 0 ? (lowStockCount / totalSkus) * 100 : 0;
  const outPct = totalSkus > 0 ? (outOfStockCount / totalSkus) * 100 : 0;

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
        <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Inventory Summary</h3>
        <Link href="/dashboard/inventory" className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
          <span>View stock</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Inventory Health Gauge — composition of healthy vs low vs out-of-stock SKUs */}
      <div className="pb-4 mb-1 border-b border-dashboard-border">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Inventory Health</span>
          <span className={`text-xs font-bold ${healthBand.color}`}>
            {totalSkus > 0 ? `${healthPct}% healthy` : healthBand.label}
          </span>
        </div>
        <div className="w-full h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-white/5 flex">
          {totalSkus === 0 ? (
            <div className="h-full w-full bg-slate-200 dark:bg-white/10" />
          ) : (
            <>
              {healthyPct > 0 && <div className="h-full bg-emerald-500" style={{ width: `${healthyPct}%` }} title={`${healthyCount} healthy`} />}
              {lowPct > 0 && <div className="h-full bg-amber-500" style={{ width: `${lowPct}%` }} title={`${lowStockCount} low stock`} />}
              {outPct > 0 && <div className="h-full bg-rose-500" style={{ width: `${outPct}%` }} title={`${outOfStockCount} out of stock`} />}
            </>
          )}
        </div>
        <div className="flex items-center gap-3 mt-2 text-[10px] font-semibold text-slate-400">
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{healthyCount} healthy</span>
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />{lowStockCount} low</span>
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-500" />{outOfStockCount} out</span>
        </div>
      </div>

      {/* Summary List with Data Bars */}
      <div className="flex-1 space-y-4 py-2">
        {/* Total SKUs */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-blue-500 bg-blue-50 dark:bg-blue-500/10">
              <Layers className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Total SKUs</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{totalSkus}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-blue-500" style={{ width: totalSkus > 0 ? "100%" : "0%" }} />
            </div>
          </div>
        </div>

        {/* Low Stock Items */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-amber-500 bg-amber-50 dark:bg-amber-500/10">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Low Stock Items</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{lowStockCount}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-amber-500" style={{ width: `${lowPct}%` }} />
            </div>
          </div>
        </div>

        {/* Out of Stock Items */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-rose-500 bg-rose-50 dark:bg-rose-500/10">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Out of Stock Items</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{outOfStockCount}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-rose-500" style={{ width: `${outPct}%` }} />
            </div>
          </div>
        </div>

        {/* Inventory Value */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10">
              <DollarSign className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Inventory Value</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
              ₹{((data?.total_inventory_value ?? 0) / 100000).toFixed(2)}L
            </span>
          </div>
        </div>
      </div>

      {/* Warning notice */}
      {data?.low_stock_count !== undefined && data.low_stock_count > 0 && (
        <div className="mt-4 p-3 bg-amber-50/70 dark:bg-amber-500/[0.08] border border-amber-200 dark:border-amber-500/20 rounded-xl flex items-center gap-2.5 text-xs text-amber-800 dark:text-amber-300">
          <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          <span>{data.low_stock_count} SKUs are below minimum stock level</span>
        </div>
      )}
    </div>
  );
}
