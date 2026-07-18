"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import { Loader2, AlertCircle, FileText, IndianRupee, LineChart, ShieldAlert } from "lucide-react";

interface TimeSeriesPoint {
  date: string;
  sales: number;
}

interface RevenueData {
  total_revenue: number;
  total_receivables: number;
  time_series: TimeSeriesPoint[];
}

export default function ReportsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RevenueData | null>(null);

  // Sync tenant from localStorage on load
  useEffect(() => {
    const currentWorkspace = localStorage.getItem("tenant_id");
    if (currentWorkspace) {
      setActiveTenantId(currentWorkspace);
    }
  }, []);

  const handleTenantChange = (id: string) => {
    setActiveTenantId(id);
    localStorage.setItem("tenant_id", id);
  };

  const getTenantName = () => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("tenant_name");
      if (stored) return stored;
    }
    return "Loading Workspace...";
  };

  const fetchRevenueAnalytics = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/analytics/revenue-trend?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to fetch revenue reports data");
      const resData = await resp.json();
      setData(resData);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load revenue reports");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    if (activeTenantId) {
      fetchRevenueAnalytics(activeTenantId);
    }
  }, [activeTenantId, fetchRevenueAnalytics]);

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      <Sidebar
        activeTab="Reports"
        setActiveTab={() => {}}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          <div>
            <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
              <FileText className="w-5 h-5 text-brand-blue" />
              <span>Financial Reports Workspace</span>
            </h1>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              Consolidate gross revenues, aggregate outstanding credit accounts, and track multi-tenant collections performance
            </p>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3">
              <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500">Aggregating database financial metrics...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3 text-rose-600">
              <AlertCircle className="w-8 h-8" />
              <span className="text-sm font-semibold">{error}</span>
              <button
                onClick={() => fetchRevenueAnalytics(activeTenantId)}
                className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Financial Accounting Grid Banners */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Gross Revenue</p>
                    <h3 className="text-2xl font-extrabold text-slate-800 mt-1">
                      {formatCurrency(data?.total_revenue || 0)}
                    </h3>
                    <p className="text-[10px] text-slate-400 font-semibold mt-1">Confirmed orders billing sum</p>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-brand-blue shadow-sm">
                    <IndianRupee className="w-5 h-5" />
                  </div>
                </div>

                <div className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Outstanding Receivables</p>
                    <h3 className="text-2xl font-extrabold text-amber-600 mt-1">
                      {formatCurrency(data?.total_receivables || 0)}
                    </h3>
                    <p className="text-[10px] text-slate-400 font-semibold mt-1">Pending collection balances</p>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 shadow-sm">
                    <ShieldAlert className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Area Time-Series Chart */}
              <div className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-[400px]">
                <h3 className="text-sm font-bold text-slate-700 mb-4 flex items-center gap-1.5">
                  <LineChart className="w-4 h-4 text-brand-blue" />
                  <span>Revenue Trend over Time (Daily Sales Volume)</span>
                </h3>
                <div className="flex-1 w-full min-h-0">
                  {data && data.time_series.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={data.time_series}
                        margin={{ top: 10, right: 30, left: 20, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(tick) => `₹${tick/1000}k`} />
                        <Tooltip
                          contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px" }}
                          formatter={(value: any) => [formatCurrency(value), "Sales"]}
                        />
                        <Area type="monotone" dataKey="sales" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorSales)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex items-center justify-center h-full text-slate-400 text-xs font-semibold">
                      No transactional sales data available.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
