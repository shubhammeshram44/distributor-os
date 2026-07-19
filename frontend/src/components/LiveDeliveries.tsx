"use client";

import React, { useState, useEffect } from "react";
import { Truck, MapPin, ArrowRight, Package, CheckCircle2 } from "lucide-react";
import Link from "next/link";

interface ShipmentItem {
  shipment_id: string;
  driver_name: string;
  vehicle_number: string;
  status: string;
  order_id: string;
  internal_order_id: string;
  customer_name: string;
  invoice_amount: number;
  is_paid: boolean;
}

interface LiveDeliveriesProps {
  viewAllHref?: string;
}

export default function LiveDeliveries({ viewAllHref }: LiveDeliveriesProps = {}) {
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchShipments = async () => {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      try {
        const resp = await fetch(`${apiBase}/api/v1/shipments/active`, {
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (resp.ok) setShipments(await resp.json());
      } catch { /* silently handle */ } finally {
        setLoading(false);
      }
    };
    fetchShipments();
  }, []);

  const statusStyle = (s: string) =>
    s.toLowerCase().includes("deliver") ? "text-emerald-400 bg-emerald-500/10"
      : s.toLowerCase().includes("out") ? "text-blue-400 bg-blue-500/10"
        : "text-amber-400 bg-amber-500/10";

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v);

  return (
    <div className="bg-dashDark-card p-5 rounded-xl border border-dashDark-border flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashDark-border mb-3">
        <div className="flex items-center gap-2">
          <h3 className="font-bold text-dashDark-text text-base">Live Deliveries</h3>
          {!loading && shipments.length > 0 && (
            <>
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
              <span className="text-xs font-semibold text-emerald-400">Live</span>
            </>
          )}
        </div>
        <Link
          href={viewAllHref || "/dashboard/shipments"}
          className="text-xs font-semibold text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1"
        >
          <span>View all</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {loading ? (
          [1, 2, 3].map((i) => <div key={i} className="animate-pulse rounded-xl h-14 bg-dashDark-cardAlt" />)
        ) : shipments.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center gap-2">
            <div className="w-10 h-10 rounded-full bg-dashDark-cardAlt flex items-center justify-center">
              <Truck className="w-5 h-5 text-dashDark-textFaint" />
            </div>
            <p className="text-sm font-semibold text-dashDark-textMuted">No active deliveries</p>
            <p className="text-xs text-dashDark-textFaint">Dispatched orders will appear here</p>
          </div>
        ) : (
          shipments.slice(0, 5).map((s) => (
            <div key={s.shipment_id} className="flex items-center gap-3 p-3 rounded-xl border border-dashDark-border hover:border-blue-500/30 hover:bg-dashDark-cardAlt transition-all">
              <div className="w-8 h-8 rounded-xl bg-dashDark-cardAlt flex items-center justify-center flex-shrink-0">
                {s.status.toLowerCase().includes("deliver")
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  : <Truck className="w-4 h-4 text-blue-400" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold text-dashDark-text truncate">{s.customer_name}</p>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${statusStyle(s.status)}`}>{s.status}</span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <Package className="w-3 h-3 text-dashDark-textFaint" />
                  <span className="text-[11px] text-dashDark-textMuted truncate">{s.internal_order_id}</span>
                  <span className="text-[11px] text-dashDark-textFaint">·</span>
                  <span className="text-[11px] text-dashDark-textMuted">{formatCurrency(s.invoice_amount)}</span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <MapPin className="w-3 h-3 text-dashDark-textFaint" />
                  <span className="text-[10px] text-dashDark-textFaint truncate">{s.driver_name} · {s.vehicle_number}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

