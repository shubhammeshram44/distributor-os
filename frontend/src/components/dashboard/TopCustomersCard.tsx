"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Users } from "lucide-react";

interface TopCustomer {
  id: string;
  retailer_name: string;
  outstanding_balance: number;
  phone: string;
}

interface TopCustomersCardProps {
  activeTenantId: string;
}

const formatCurrency = (value: number) =>
  `₹${value >= 100000 ? `${(value / 100000).toFixed(1)}L` : value.toLocaleString("en-IN")}`;

const initials = (name: string) =>
  name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");

/**
 * Top 5 customers by outstanding balance — sourced from the existing,
 * already-registered /api/v1/customers endpoint with sort_by=outstanding_balance.
 * Intentionally labeled by outstanding balance (not "MTD sales"), since no
 * per-customer MTD sales aggregation exists in the backend.
 */
export default function TopCustomersCard({ activeTenantId }: TopCustomersCardProps) {
  const [customers, setCustomers] = useState<TopCustomer[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!activeTenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const token = localStorage.getItem("accessToken");
    setIsLoading(true);
    fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}&sort_by=outstanding_balance&sort_order=desc&limit=5`, {
      credentials: "include",
      headers: token ? { Authorization: "Bearer " + token } : {}
    })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setCustomers(d.items || []))
      .catch(() => setCustomers([]))
      .finally(() => setIsLoading(false));
  }, [activeTenantId]);

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-dashDark-text text-sm">Top Customers by Outstanding</h3>
        <Users className="w-4 h-4 text-dashDark-textMuted" />
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse flex-1">
          {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-dashDark-cardAlt rounded-lg" />)}
        </div>
      ) : customers.filter((c) => c.outstanding_balance > 0).length === 0 ? (
        <p className="text-xs text-dashDark-textMuted flex-1 flex items-center justify-center">No outstanding dues</p>
      ) : (
        <div className="space-y-1 flex-1">
          {customers.filter((c) => c.outstanding_balance > 0).map((customer) => (
            <Link
              key={customer.id}
              href={`/dashboard/customers/${customer.id}`}
              className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-dashDark-cardAlt transition-all group"
            >
              <div className="w-7 h-7 rounded-full bg-brand-blue/15 text-brand-blue flex items-center justify-center text-[10px] font-bold shrink-0">
                {initials(customer.retailer_name)}
              </div>
              <span className="text-xs font-semibold text-dashDark-text truncate flex-1 group-hover:text-brand-blue">
                {customer.retailer_name}
              </span>
              <span className="text-[11px] font-bold text-amber-400 shrink-0">
                {formatCurrency(customer.outstanding_balance)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
