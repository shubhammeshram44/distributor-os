"use client";

import React, { useEffect, useState } from "react";
import { Rocket, Package, UserPlus, ShoppingCart, CheckCircle2, ChevronRight, X } from "lucide-react";
import Link from "next/link";

interface GettingStartedStripProps {
  activeTenantId: string;
  hasProducts: boolean;
  hasOrders: boolean;
  hasConfirmedOrder: boolean;
}

const DISMISS_KEY = "dashboard_getting_started_dismissed";

/**
 * Horizontal onboarding progress strip. Every step reflects real, verifiable
 * tenant state — there is no fabricated "N% ready" number:
 *  - hasProducts / hasOrders / hasConfirmedOrder come from already-fetched
 *    dashboard metrics + recent orders (no extra network calls).
 *  - hasCustomers is fetched here once from the existing customers list
 *    endpoint (reusing `total` from its pagination envelope).
 */
export default function GettingStartedStrip({
  activeTenantId,
  hasProducts,
  hasOrders,
  hasConfirmedOrder
}: GettingStartedStripProps) {
  const [hasCustomers, setHasCustomers] = useState<boolean | null>(null);
  const [dismissed, setDismissed] = useState(true); // default hidden until localStorage checked, avoids flash

  useEffect(() => {
    setDismissed(localStorage.getItem(DISMISS_KEY) === "true");
  }, []);

  useEffect(() => {
    if (!activeTenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const token = localStorage.getItem("accessToken");
    fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}&limit=1`, {
      credentials: "include",
      headers: token ? { Authorization: "Bearer " + token } : {}
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setHasCustomers(!!d && (d.total ?? 0) > 0))
      .catch(() => setHasCustomers(null));
  }, [activeTenantId]);

  const steps = [
    { label: "Add your first product", icon: Package, done: hasProducts, href: "/dashboard/products" },
    { label: "Add your first customer", icon: UserPlus, done: !!hasCustomers, href: "/dashboard/customers" },
    { label: "Create your first order", icon: ShoppingCart, done: hasOrders, href: "/dashboard/orders" },
    { label: "Confirm an order", icon: CheckCircle2, done: hasConfirmedOrder, href: "/dashboard/orders" },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  const allComplete = completedCount === steps.length;

  // Nothing to show once every step is done AND the user dismissed it, or before
  // we've resolved the customer-count signal (avoids a flash of "0 of 4").
  if (dismissed || hasCustomers === null) return null;

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex items-center gap-3 shrink-0 sm:w-56">
        <div className="w-10 h-10 rounded-lg bg-brand-blue/15 flex items-center justify-center shrink-0">
          <Rocket className="w-5 h-5 text-brand-blue" />
        </div>
        <div>
          <p className="text-sm font-bold text-dashDark-text">Getting Started</p>
          <p className="text-[11px] text-dashDark-textMuted">{completedCount} of {steps.length} completed</p>
        </div>
      </div>

      <div className="flex-1 h-1.5 bg-dashDark-cardAlt rounded-full overflow-hidden hidden sm:block">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      <div className="flex items-center gap-2 overflow-x-auto">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <Link
              key={step.label}
              href={step.href}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all shrink-0 ${
                step.done
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-dashDark-cardAlt text-dashDark-textMuted hover:text-dashDark-text"
              }`}
            >
              {step.done ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Icon className="w-3.5 h-3.5" />}
              <span>{step.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        {allComplete && (
          <button
            onClick={() => { localStorage.setItem(DISMISS_KEY, "true"); setDismissed(true); }}
            className="text-dashDark-textMuted hover:text-dashDark-text p-1.5 rounded-lg transition-all"
            aria-label="Dismiss getting started checklist"
            title="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        <ChevronRight className="w-4 h-4 text-dashDark-textFaint hidden sm:block" />
      </div>
    </div>
  );
}
