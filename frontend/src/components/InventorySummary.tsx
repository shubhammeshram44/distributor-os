"use client";

import React from "react";
import { AlertCircle, Layers, CheckCircle2, DollarSign, ArrowRight } from "lucide-react";
import Link from "next/link";

interface InventorySummaryProps {
  totalSkus?: number;
  lowStock?: number;
  outOfStock?: number;
  inventoryValue?: string;
}

export default function InventorySummary({
  totalSkus = 4285,
  lowStock = 128,
  outOfStock = 27,
  inventoryValue = "₹ 8.52 Cr"
}: InventorySummaryProps) {
  const summaryItems = [
    { label: "Total SKUs", value: totalSkus.toLocaleString(), color: "bg-blue-500", icon: Layers, iconColor: "text-blue-500 bg-blue-50" },
    { label: "Low Stock Items", value: lowStock.toLocaleString(), color: "bg-amber-500", icon: AlertCircle, iconColor: "text-amber-500 bg-amber-50" },
    { label: "Out of Stock Items", value: outOfStock.toLocaleString(), color: "bg-rose-500", icon: AlertCircle, iconColor: "text-rose-500 bg-rose-50" },
    { label: "Inventory Value", value: inventoryValue, color: "bg-emerald-500", icon: DollarSign, iconColor: "text-emerald-500 bg-emerald-50" }
  ];

  return (
    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
        <h3 className="font-bold text-slate-800 text-base">Inventory Summary</h3>
        <Link href="/dashboard/inventory" className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
          <span>View stock</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Summary List with Data Bars */}
      <div className="flex-1 space-y-4 py-2">
        {summaryItems.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div key={idx} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${item.iconColor}`}>
                  <Icon className="w-4.5 h-4.5" />
                </div>
                <span className="text-sm font-semibold text-slate-600">{item.label}</span>
              </div>
              
              <div className="flex items-center gap-3 text-right">
                <span className="text-sm font-bold text-slate-800">{item.value}</span>
                {/* Visual indicator bar */}
                <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden hidden sm:block">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{
                      width: item.label.includes("Total")
                        ? "90%"
                        : item.label.includes("Low")
                        ? "35%"
                        : item.label.includes("Out")
                        ? "10%"
                        : "70%"
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Warning notice */}
      <div className="mt-4 p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center gap-2.5 text-xs text-amber-800">
        <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
        <span className="font-semibold">12 SKUs are below minimum stock level</span>
      </div>
    </div>
  );
}
