"use client";

import React from "react";
import Link from "next/link";
import { PackagePlus, UserPlus, ReceiptText, ClipboardList, BarChart3, MessageSquarePlus } from "lucide-react";

interface QuickActionsGridProps {
  onNewOrder: () => void;
}

const actions = (onNewOrder: () => void) => [
  { label: "New Order", icon: MessageSquarePlus, color: "text-emerald-400 bg-emerald-500/10", onClick: onNewOrder },
  { label: "Add Product", icon: PackagePlus, color: "text-blue-400 bg-blue-500/10", href: "/dashboard/products" },
  { label: "Add Customer", icon: UserPlus, color: "text-violet-400 bg-violet-500/10", href: "/dashboard/customers" },
  { label: "Record Payment", icon: ReceiptText, color: "text-amber-400 bg-amber-500/10", href: "/dashboard/collections" },
  { label: "Stock Update", icon: ClipboardList, color: "text-orange-400 bg-orange-500/10", href: "/dashboard/inventory" },
  { label: "View Reports", icon: BarChart3, color: "text-teal-400 bg-teal-500/10", href: "/dashboard/reports" },
];

/** Icon-grid of real, working navigation shortcuts — every tile links to (or
 * triggers) an existing production feature; nothing here is decorative. */
export default function QuickActionsGrid({ onNewOrder }: QuickActionsGridProps) {
  const items = actions(onNewOrder);

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <h3 className="font-bold text-dashDark-text text-sm mb-4">Quick Actions</h3>
      <div className="grid grid-cols-3 gap-2.5 flex-1">
        {items.map((item) => {
          const Icon = item.icon;
          const content = (
            <>
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${item.color}`}>
                <Icon className="w-4.5 h-4.5" />
              </div>
              <span className="text-[11px] font-semibold text-dashDark-textMuted text-center leading-tight">{item.label}</span>
            </>
          );
          const className = "flex flex-col items-center justify-center gap-1.5 p-2.5 rounded-lg border border-dashDark-border hover:border-brand-blue/40 hover:bg-dashDark-cardAlt transition-all";

          return item.href ? (
            <Link key={item.label} href={item.href} className={className}>
              {content}
            </Link>
          ) : (
            <button key={item.label} onClick={item.onClick} className={className}>
              {content}
            </button>
          );
        })}
      </div>
    </div>
  );
}
