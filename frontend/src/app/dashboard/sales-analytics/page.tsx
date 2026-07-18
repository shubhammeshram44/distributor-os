"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from "recharts";
import { Loader2, AlertCircle, BarChart3, TrendingUp, ShoppingBag, Layers } from "lucide-react";

interface SKUData {
  sku_code: string;
  brand: string;
  category: string;
  total_quantity: number;
}

interface AnalyticsData {
  total_orders: number;
  status_distribution: {
    [key: string]: number;
  };
  top_moving_skus: SKUData[];
}

export default function SalesAnalyticsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [timeframe, setTimeframe] = useState("7d");
  const [perfMetrics, setPerfMetrics] = useState<{
    total_sales: number;
    total_sales_change: number;
    orders_count: number;
    orders_count_change: number;
    average_order_value: number;
    average_order_value_change: number;
  } | null>(null);

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

  const fetchSalesAnalytics = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/analytics/sales-overview?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to fetch sales analytics");
      const resData = await resp.json();
      setData(resData);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load sales analytics");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    if (activeTenantId) {
      fetchSalesAnalytics(activeTenantId);
    }
  }, [activeTenantId, fetchSalesAnalytics]);

  const fetchPerfMetrics = useCallback(async () => {
    if (!activeTenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const now = new Date();
    const days = timeframe === "7d" ? 7 : timeframe === "30d" ? 30 : 90;
    const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
      .toISOString().split("T")[0];
    const endDate = now.toISOString().split("T")[0];
    
    try {
      const res = await fetch(
        `${apiBase}/api/v1/dashboard/metrics?tenant_id=${activeTenantId}&start_date=${startDate}&end_date=${endDate}`,
        { credentials: "include" }
      );
      if (res.ok) {
        const resData = await res.json();
        setPerfMetrics(resData);
      }
    } catch (err) {
      console.error("Error fetching performance metrics:", err);
    }
  }, [activeTenantId, timeframe]);

  useEffect(() => {
    fetchPerfMetrics();
  }, [fetchPerfMetrics]);

  // Transform pie data
  const pieData = data
    ? Object.entries(data.status_distribution).map(([name, value]) => ({
        name,
        value
      }))
    : [];

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-dashboard-inset">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800 dark:text-slate-100">
      <Sidebar
        activeTab="Sales Analytics"
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
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-brand-blue" />
                <span>Sales Analytics Workspace</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Analyze product performance rankings, sales velocities, and dynamic pipeline fulfillment statuses
              </p>
            </div>
            
            {/* Timeframe Selector */}
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="border border-slate-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm text-slate-700 dark:text-slate-300 outline-none focus:border-emerald-500 bg-white dark:bg-dashboard-card cursor-pointer shadow-sm"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
          </div>

          {/* Performance Cards */}
          {perfMetrics && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  label: "Total Sales",
                  value: `₹${(perfMetrics.total_sales || 0).toLocaleString("en-IN")}`,
                  change: perfMetrics.total_sales_change || 0,
                  icon: "₹"
                },
                {
                  label: "Orders Count",
                  value: (perfMetrics.orders_count || 0).toString(),
                  change: perfMetrics.orders_count_change || 0,
                  icon: "🛒"
                },
                {
                  label: "Average Order Value",
                  value: `₹${(perfMetrics.average_order_value || 0).toLocaleString("en-IN")}`,
                  change: perfMetrics.average_order_value_change || 0,
                  icon: "📊"
                }
              ].map((card) => (
                <div key={card.label} className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-5 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                      {card.label}
                    </span>
                    <span className="text-lg">{card.icon}</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{card.value}</div>
                  <div className={`text-xs font-semibold mt-1 ${
                    card.change >= 0 ? "text-emerald-600" : "text-red-500"
                  }`}>
                    {card.change >= 0 ? "↑" : "↓"}{Math.abs(card.change).toFixed(1)}% vs previous period
                  </div>
                </div>
              ))}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3">
              <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500 dark:text-slate-500">Aggregating database sales metrics...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3 text-rose-600">
              <AlertCircle className="w-8 h-8" />
              <span className="text-sm font-semibold">{error}</span>
              <button
                onClick={() => fetchSalesAnalytics(activeTenantId)}
                className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Analytics Summary Banners */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Sales Orders</p>
                    <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">{data?.total_orders}</h3>
                    <p className="text-[10px] text-slate-400 font-semibold mt-1">Processed in current tenant context</p>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-brand-blue shadow-sm">
                    <ShoppingBag className="w-5 h-5" />
                  </div>
                </div>

                <div className="bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Top Brand Volume</p>
                    <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">
                      {data?.top_moving_skus[0]?.brand || "N/A"}
                    </h3>
                    <p className="text-[10px] text-slate-400 font-semibold mt-1">Leading product catalog manufacturer</p>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 shadow-sm">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Data Visualization Sections */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top Moving SKUs */}
                <div className="bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-[400px]">
                  <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-brand-blue" />
                    <span>Top-Moving SKUs (By Quantity)</span>
                  </h3>
                  <div className="flex-1 w-full min-h-0">
                    {data && data.top_moving_skus.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={data.top_moving_skus}
                          layout="vertical"
                          margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
                        >
                          <XAxis type="number" stroke="#94a3b8" fontSize={10} />
                          <YAxis dataKey="sku_code" type="category" stroke="#94a3b8" fontSize={10} width={100} />
                          <Tooltip
                            contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "8px", color: "var(--color-text)" }}
                            labelStyle={{ fontWeight: "bold", color: "var(--color-text)" }}
                          />
                          <Bar dataKey="total_quantity" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={15} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-slate-400 text-xs font-semibold">
                        No products moved yet.
                      </div>
                    )}
                  </div>
                </div>

                {/* Pipeline Velocity Breakdown */}
                <div className="bg-white dark:bg-dashboard-card p-6 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-[400px]">
                  <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-brand-blue" />
                    <span>Order Pipeline Velocity Breakdown</span>
                  </h3>
                  <div className="flex-1 w-full min-h-0 flex items-center justify-center">
                    {pieData.length > 0 && pieData.some(d => d.value > 0) ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={100}
                            paddingAngle={3}
                            dataKey="value"
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "8px", color: "var(--color-text)" }}
                          />
                          <Legend verticalAlign="bottom" height={36} iconType="circle" />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-slate-400 text-xs font-semibold">
                        No orders in the pipeline.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
