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

      {/* Summary List with Data Bars */}
      <div className="flex-1 space-y-4 py-2">
        {/* Total SKUs */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-blue-500 bg-blue-50">
              <Layers className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Total SKUs</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{data?.total_skus ?? 0}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-blue-500" style={{ width: "90%" }} />
            </div>
          </div>
        </div>

        {/* Low Stock Items */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-amber-500 bg-amber-50">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Low Stock Items</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{data?.low_stock_count ?? 0}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-amber-500" style={{ width: "35%" }} />
            </div>
          </div>
        </div>

        {/* Out of Stock Items */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-rose-500 bg-rose-50">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Out of Stock Items</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{data?.out_of_stock_count ?? 0}</span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-rose-500" style={{ width: "10%" }} />
            </div>
          </div>
        </div>

        {/* Inventory Value */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-emerald-500 bg-emerald-50">
              <DollarSign className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">Inventory Value</span>
          </div>
          
          <div className="flex items-center gap-3 text-right">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
              ₹{((data?.total_inventory_value ?? 0) / 100000).toFixed(2)}L
            </span>
            <div className="w-16 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden hidden sm:block">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: "70%" }} />
            </div>
          </div>
        </div>
      </div>

      {/* Warning notice */}
      {data?.low_stock_count !== undefined && data.low_stock_count > 0 && (
        <div className="mt-4 p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center gap-2.5 text-xs text-amber-800">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{data.low_stock_count} SKUs are below minimum stock level</span>
        </div>
      )}
    </div>
  );
}
