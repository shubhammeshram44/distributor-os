"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, PackageX, Clock, ChevronRight } from "lucide-react";

interface AlertsNotificationsCardProps {
  pendingOrdersCount: number;
  lowStockCount: number;
  outOfStockCount: number;
  overdue60Count: number;
}

/**
 * Actionable alerts derived entirely from real metrics already available on
 * the dashboard (status_distribution.Pending from sales-overview, and
 * low_stock/out_of_stock/overdue_60 counts from /metrics) — no synthetic data.
 */
export default function AlertsNotificationsCard({
  pendingOrdersCount,
  lowStockCount,
  outOfStockCount,
  overdue60Count
}: AlertsNotificationsCardProps) {
  const alerts = [
    pendingOrdersCount > 0 && {
      icon: Clock,
      color: "text-amber-400 bg-amber-500/10",
      text: `${pendingOrdersCount} order${pendingOrdersCount === 1 ? "" : "s"} awaiting confirmation`,
      href: "/dashboard/orders?status=pending",
    },
    outOfStockCount > 0 && {
      icon: PackageX,
      color: "text-rose-400 bg-rose-500/10",
      text: `${outOfStockCount} SKU${outOfStockCount === 1 ? "" : "s"} out of stock`,
      href: "/dashboard/inventory?filter=out_of_stock",
    },
    lowStockCount > 0 && {
      icon: AlertTriangle,
      color: "text-orange-400 bg-orange-500/10",
      text: `${lowStockCount} SKU${lowStockCount === 1 ? "" : "s"} running low on stock`,
      href: "/dashboard/inventory?filter=low_stock",
    },
    overdue60Count > 0 && {
      icon: AlertTriangle,
      color: "text-rose-400 bg-rose-500/10",
      text: `${overdue60Count} customer${overdue60Count === 1 ? "" : "s"} with 60+ day overdue dues`,
      href: "/dashboard/collections?filter=overdue_60",
    },
  ].filter(Boolean) as { icon: typeof Clock; color: string; text: string; href: string }[];

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-dashDark-text text-sm">Alerts</h3>
        {alerts.length > 0 && (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-400">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-4">
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center mb-2">
            <span className="text-emerald-400 text-lg">✓</span>
          </div>
          <p className="text-xs text-dashDark-textMuted font-semibold">All clear — nothing needs attention</p>
        </div>
      ) : (
        <div className="space-y-2 flex-1">
          {alerts.map((alert, i) => {
            const Icon = alert.icon;
            return (
              <Link
                key={i}
                href={alert.href}
                className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-dashDark-cardAlt transition-all group"
              >
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${alert.color}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <span className="text-xs font-semibold text-dashDark-textMuted group-hover:text-dashDark-text flex-1">
                  {alert.text}
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-dashDark-textFaint" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
