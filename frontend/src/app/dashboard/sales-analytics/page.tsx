"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { ChartSkeleton } from "@/components/Skeletons";
import ErrorBoundary from "@/components/ErrorBoundary";
import { AlertCircle, TrendingUp, DollarSign, Users, ShoppingCart } from "lucide-react";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

export default function SalesAnalyticsPage() {
  const [tenantId, setTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("30");
  const [analyticsData, setAnalyticsData] = useState<any>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;

  useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) setTenantId(storedTenant);
  }, []);

  const fetchAnalytics = useCallback(async () => {
    if (!tenantId) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        tenant_id: tenantId,
        days: timeRange
      });

      const response = await fetch(`${apiBase}/api/v1/analytics/sales?${params}`, {
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` })
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAnalyticsData(data);
      } else {
        setError("Failed to load analytics");
      }
    } catch (err) {
      setError("Network error");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [tenantId, apiBase, token, timeRange]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // Mock data for visualization
  const salesTrendData = [
    { date: "Mon", sales: 4000, orders: 24 },
    { date: "Tue", sales: 3000, orders: 13 },
    { date: "Wed", sales: 2000, orders: 9 },
    { date: "Thu", sales: 2780, orders: 39 },
    { date: "Fri", sales: 1890, orders: 22 },
    { date: "Sat", sales: 2390, orders: 22 },
    { date: "Sun", sales: 3490, orders: 20 }
  ];

  const categorySalesData = [
    { name: "Electronics", value: 35 },
    { name: "Grocery", value: 25 },
    { name: "Apparel", value: 20 },
    { name: "Others", value: 20 }
  ];

  const colors = ["#1e62ec", "#10b981", "#f59e0b", "#ef4444"];

  const kpiCards = [
    {
      title: "Total Sales",
      value: "₹45.2L",
      change: "+12.5%",
      icon: DollarSign,
      color: "emerald"
    },
    {
      title: "Total Orders",
      value: "1,234",
      change: "+8.2%",
      icon: ShoppingCart,
      color: "blue"
    },
    {
      title: "Avg Order Value",
      value: "₹3,670",
      change: "+2.1%",
      icon: TrendingUp,
      color: "purple"
    },
    {
      title: "Unique Customers",
      value: "456",
      change: "+5.3%",
      icon: Users,
      color: "amber"
    }
  ];

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Sales Analytics" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-800">Sales Analytics</h1>
                <p className="text-xs text-slate-400 font-semibold mt-1">Track sales performance and trends</p>
              </div>
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="px-4 py-2.5 border border-dashboard-border rounded-lg text-sm bg-white hover:bg-slate-50 cursor-pointer outline-none"
              >
                <option value="7">Last 7 Days</option>
                <option value="30">Last 30 Days</option>
                <option value="90">Last 90 Days</option>
              </select>
            </div>

            {error && (
              <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-800">{error}</p>
                  <button onClick={fetchAnalytics} className="text-xs font-semibold text-rose-600 hover:text-rose-700 mt-1 underline">
                    Try again
                  </button>
                </div>
              </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {kpiCards.map((card, idx) => {
                const Icon = card.icon;
                const colorClasses = {
                  emerald: "bg-emerald-50 text-emerald-600",
                  blue: "bg-blue-50 text-blue-600",
                  purple: "bg-purple-50 text-purple-600",
                  amber: "bg-amber-50 text-amber-600"
                };

                return (
                  <div key={idx} className="bg-white p-6 rounded-lg border border-dashboard-border shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-xs font-semibold text-slate-400 uppercase">{card.title}</span>
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorClasses[card.color as keyof typeof colorClasses]}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                    </div>
                    <p className="text-2xl font-bold text-slate-800">{card.value}</p>
                    <p className="text-xs text-emerald-600 font-semibold mt-2">{card.change} from last period</p>
                  </div>
                );
              })}
            </div>

            {/* Sales Trend Chart */}
            {loading ? (
              <ChartSkeleton />
            ) : (
              <div className="bg-white rounded-lg border border-dashboard-border shadow-sm p-6">
                <h2 className="text-lg font-bold text-slate-800 mb-4">Sales Trend</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={salesTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="sales" stroke="#1e62ec" strokeWidth={2} dot={{ fill: "#1e62ec" }} />
                    <Line type="monotone" dataKey="orders" stroke="#10b981" strokeWidth={2} dot={{ fill: "#10b981" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Sales by Category & Top Products */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Category Breakdown */}
              {loading ? (
                <ChartSkeleton />
              ) : (
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm p-6">
                  <h2 className="text-lg font-bold text-slate-800 mb-4">Sales by Category</h2>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={categorySalesData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry) => `${entry.name}: ${entry.value}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {categorySalesData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `${value}%`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Top Products Table */}
              {loading ? (
                <ChartSkeleton />
              ) : (
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm p-6">
                  <h2 className="text-lg font-bold text-slate-800 mb-4">Top Products</h2>
                  <div className="space-y-3">
                    {[
                      { name: "Product A", sales: "₹12.5L", orders: 156 },
                      { name: "Product B", sales: "₹10.2L", orders: 128 },
                      { name: "Product C", sales: "₹8.9L", orders: 95 },
                      { name: "Product D", sales: "₹7.6L", orders: 82 }
                    ].map((product, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                        <div>
                          <p className="text-sm font-semibold text-slate-800">{product.name}</p>
                          <p className="text-xs text-slate-500">{product.orders} orders</p>
                        </div>
                        <p className="text-sm font-bold text-slate-800">{product.sales}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </ErrorBoundary>
  );
}
