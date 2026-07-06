"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
// MetricCards inlined locally to format change percentages to 1 decimal place
import RecentOrders from "@/components/RecentOrders";
import CollectionsDonut from "@/components/CollectionsDonut";
// LiveDeliveries import removed 2026-06-28 — replaced by DemandGapCard in the bottom grid.
// The component file (LiveDeliveries.tsx) is preserved on disk for future use.
import InventorySummary from "@/components/InventorySummary";
import DemandGapCard from "@/components/DemandGapCard";
import ActivityFeed from "@/components/ActivityFeed";
import OnboardingChecklist from "@/components/OnboardingChecklist";
import { useDashboardData, DashboardMetrics } from "@/hooks/useDashboardData";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { ChevronDown, SlidersHorizontal, RefreshCw, CheckCircle2, AlertCircle, X, TrendingUp, TrendingDown, IndianRupee, ShoppingBag, BarChart, CreditCard } from "lucide-react";
import WhatsAppSimulator from "@/components/WhatsAppSimulator";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [tenantId, setTenantId] = useState("");
  const [userProfile, setUserProfile] = useState<any>(null);
  const [isHydrating, setIsHydrating] = useState(true);

  // Sync profile and tenant from backend / localStorage
  useEffect(() => {
    const fetchProfileAndTenant = async () => {
      try {
        const storedTenant = localStorage.getItem("tenant_id");
        if (storedTenant) {
          setTenantId(storedTenant);
        }

        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const token = localStorage.getItem("accessToken");

        const resp = await fetch(`${apiBase}/api/v1/auth/me`, {
          method: "GET",
          credentials: "include",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
          }
        });

        if (resp.status === 401) {
          localStorage.removeItem("tenant_id");
          localStorage.removeItem("tenant_name");
          window.location.href = "/auth";
          return;
        }

        if (resp.ok) {
          const profileData = await resp.json();
          setUserProfile(profileData);
          if (profileData.tenant?.name) {
            localStorage.setItem("tenant_name", profileData.tenant.name);
          }

          if (!storedTenant && profileData.tenant?.id) {
            setTenantId(profileData.tenant.id);
            localStorage.setItem("tenant_id", profileData.tenant.id);
          }
        }
      } catch (err) {
        console.error("Failed to load authenticated user profile:", err);
        window.location.href = "/auth";
        return;
      } finally {
        setIsHydrating(false);
      }
    };

    fetchProfileAndTenant();
  }, []);

  const handleTenantChange = (id: string) => {
    setTenantId(id);
    localStorage.setItem("tenant_id", id);
  };

  const [toast, setToast] = useState<{ show: boolean; message: string; type: "success" | "error" }>({
    show: false,
    message: "",
    type: "success"
  });

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast(prev => ({ ...prev, show: false }));
    }, 4000);
  };

  const getTenantName = () => {
    if (userProfile?.tenant?.name) {
      return userProfile.tenant.name;
    }
    return "Loading Workspace...";
  };

  const [timeframe, setTimeframe] = useState("7days");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split("T")[0];
  });

  const handleTimeframeChange = (value: string) => {
    const today = new Date();
    const formatDate = (date: Date) => date.toISOString().split("T")[0];

    if (value === "7days") {
      const pastDate = new Date();
      pastDate.setDate(today.getDate() - 7);
      setStartDate(formatDate(pastDate));
      setEndDate(formatDate(today));
    } else if (value === "30days") {
      const pastDate = new Date();
      pastDate.setDate(today.getDate() - 30);
      setStartDate(formatDate(pastDate));
      setEndDate(formatDate(today));
    } else if (value === "thisMonth") {
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
      setStartDate(formatDate(firstDay));
      setEndDate(formatDate(today));
    } else if (value === "custom") {
      setStartDate("");
      setEndDate("");
    }
  };

  const {
    metrics,
    recentOrders,
    donutData,
    activities,
    selectedOrderDetails,
    loadingDetails,
    fetchOrderDetails,
    closeDetails,
    refreshAll,
    error
  } = useDashboardData(isHydrating ? "" : tenantId, startDate, endDate);

  if (!tenantId || tenantId === "") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      {/* 1. Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        tenantName={getTenantName()}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        {/* 2. Top Header */}
        <DashboardHeader
          activeTenantId={tenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
          userProfile={userProfile}
        />

        {/* 3. Dashboard Scrollable Content */}
        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {isHydrating ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3 bg-white rounded-xl border border-dashboard-border shadow-sm h-[400px]">
              <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500">Hydrating your workspace profile...</span>
            </div>
          ) : (
            <>
              {/* Dashboard Control Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-slate-800 tracking-tight">Dashboard</h1>
                  <p className="text-xs text-slate-400 font-semibold mt-0.5">Real-time operational workflow management</p>
                </div>

                {/* Date Picker & Action Controls */}
                <div className="flex items-center gap-3">
                  {/* Unified Timeframe Selector */}
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-semibold text-slate-500">Timeframe:</label>
                    <select
                      value={timeframe}
                      onChange={(e) => {
                        setTimeframe(e.target.value);
                        handleTimeframeChange(e.target.value);
                      }}
                      className="bg-white border border-slate-200 text-slate-700 text-xs font-bold rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all cursor-pointer outline-none"
                    >
                      <option value="7days">Last 7 Days</option>
                      <option value="30days">Last 30 Days</option>
                      <option value="thisMonth">This Month</option>
                      <option value="custom">Custom Range</option>
                    </select>
                  </div>

                  {timeframe === "custom" && (
                    <div className="flex items-center gap-2 animate-fade-in">
                      <div className="flex items-center gap-1.5 bg-white border border-dashboard-border rounded-lg px-2.5 py-1.5 shadow-sm">
                        <span className="text-[10px] uppercase font-bold text-slate-400">From</span>
                        <input
                          type="date"
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="text-xs font-semibold text-slate-600 bg-transparent focus:outline-none cursor-pointer"
                        />
                      </div>
                      <div className="flex items-center gap-1.5 bg-white border border-dashboard-border rounded-lg px-2.5 py-1.5 shadow-sm">
                        <span className="text-[10px] uppercase font-bold text-slate-400">To</span>
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="text-xs font-semibold text-slate-600 bg-transparent focus:outline-none cursor-pointer"
                        />
                      </div>
                      {(startDate || endDate) && (
                        <button
                          onClick={() => {
                            setStartDate("");
                            setEndDate("");
                          }}
                          className="p-1.5 text-slate-400 hover:text-slate-600 bg-white border border-dashboard-border rounded-lg shadow-sm"
                          title="Clear date filters"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  )}

                  {/* Customize Layout Button */}
                  <button className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
                    <span>Customize</span>
                  </button>
                </div>
              </div>

              {/* API Error Banner */}
              {error && (
                <ErrorBanner
                  message={`Dashboard data could not be loaded: ${error}`}
                  onRetry={() => refreshAll()}
                />
              )}

              {/* Getting Started checklist — only renders for a brand-new,
                  unfinished workspace; disappears once dismissed or complete. */}
              <OnboardingChecklist activeTenantId={tenantId} />

              {/* A. Core Operational Metrics Row */}
              <MetricCards metrics={metrics} />

              {/* B. Split Middle Pane (Recent Orders vs Collections Aging Donut) */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* Left Col: Recent Orders Table (60% width) */}
                <div className="lg:col-span-3 min-h-[380px]">
                  <RecentOrders
                    orders={recentOrders}
                    fetchOrderDetails={fetchOrderDetails}
                    selectedOrderDetails={selectedOrderDetails}
                    loadingDetails={loadingDetails}
                    closeDetails={closeDetails}
                    onSuccess={(msg) => {
                      showToast(msg, "success");
                      refreshAll();
                    }}
                    onError={(msg) => {
                      showToast(msg, "error");
                      console.error("Inventory/Order Adjustment Exception:", msg);
                    }}
                    activeTenantId={tenantId}
                    viewAllHref="/dashboard/orders"
                  />
                </div>

                {/* Right Col: Collections Donut Chart (40% width) */}
                <div className="lg:col-span-2 min-h-[380px]">
                  <CollectionsDonut
                    data={donutData}
                    viewReportHref="/dashboard/collections"
                    overdue60Count={metrics?.overdue_60_count}
                  />
                </div>
              </div>

              {/* C. Bottom Operational Grid (Demand Gap, Stock Summary, Activity Feed) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="min-h-[300px]">
                  {/* DemandGapCard replaces LiveDeliveries (2026-06-28) */}
                  <DemandGapCard activeTenantId={tenantId} />
                </div>
                <div className="min-h-[300px]">
                  <InventorySummary data={metrics || undefined} />
                </div>
                <div className="min-h-[300px]">
                  <ActivityFeed activities={activities} viewAllHref="/dashboard/reports" />
                </div>
              </div>
            </>
          )}
        </main>
      </div>

      {/* WhatsApp Ingestion Live testing simulator */}
      <WhatsAppSimulator
        activeTenantId={tenantId}
        onSuccess={refreshAll}
      />

      {/* Sleek Floating Toast Notification */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 backdrop-blur-md border border-slate-100 shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-sm">
          {toast.type === "success" ? (
            <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0 shadow-sm">
              <CheckCircle2 className="w-4.5 h-4.5" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-rose-600 shrink-0 shadow-sm">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-slate-800">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-slate-500 font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 transition-all shrink-0"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

interface MetricCardsProps {
  metrics: DashboardMetrics | null;
}

function MetricCards({ metrics }: MetricCardsProps) {
  // Format numbers to Indian currency system (e.g. ₹ 28,45,600)
  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  const formatNumber = (val: number) => {
    return new Intl.NumberFormat("en-IN").format(val);
  };

  if (!metrics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm animate-pulse h-32" />
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: "Total Sales (This Week)",
      value: formatCurrency(metrics.total_sales),
      change: metrics.total_sales_change,
      isPositive: metrics.total_sales_change >= 0,
      subtext: "vs 14 May – 20 May, 2025",
      icon: IndianRupee,
      iconBg: "bg-emerald-50 text-emerald-600",
      strokeColor: "#10b981",
      sparklinePath: "M0,25 Q15,5 30,20 T60,10 T95,15 T130,5 T160,18" // green sparkline
    },
    {
      title: "Orders Count",
      value: formatNumber(metrics.orders_count),
      change: metrics.orders_count_change,
      isPositive: metrics.orders_count_change >= 0,
      subtext: "vs last week",
      icon: ShoppingBag,
      iconBg: "bg-blue-50 text-blue-600",
      strokeColor: "#3b82f6",
      sparklinePath: "M0,20 Q15,28 30,10 T60,25 T90,5 T120,15 T160,8" // blue sparkline
    },
    {
      title: "Average Order Value",
      value: formatCurrency(metrics.average_order_value),
      change: metrics.average_order_value_change,
      isPositive: metrics.average_order_value_change >= 0,
      subtext: "vs last week",
      icon: BarChart,
      iconBg: "bg-purple-50 text-purple-600",
      strokeColor: "#8b5cf6",
      sparklinePath: "M0,28 Q20,15 40,25 T80,10 T120,20 T160,12" // purple sparkline
    },
    {
      title: "Outstanding Collections",
      value: formatCurrency(metrics.outstanding_collections),
      change: Math.abs(metrics.outstanding_collections_change),
      isPositive: metrics.outstanding_collections_change < 0,
      subtext: "vs last week",
      icon: CreditCard,
      iconBg: "bg-orange-50 text-orange-600",
      strokeColor: "#f97316",
      sparklinePath: "M0,15 Q20,30 40,10 T80,25 T120,5 T160,20" // orange sparkline
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {cards.map((metric, i) => {
        const Icon = metric.icon;
        return (
          <div key={i} className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between hover:shadow-md transition-all">
            {/* Top Row */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center">
                {metric.title}
              </span>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${metric.iconBg}`}>
                <Icon className="w-4.5 h-4.5" />
              </div>
            </div>

            {/* Value and Trend Indicator */}
            <div className="mt-3 flex items-baseline gap-2">
              <h2 className="text-xl font-bold text-slate-800 tracking-tight">{metric.value}</h2>
              <div className={`flex items-center gap-0.5 text-xs font-bold ${
                metric.isPositive ? "text-emerald-600" : "text-rose-600"
              }`}>
                {metric.isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                <span>{parseFloat(String(metric.change)).toFixed(1)}%</span>
              </div>
            </div>

            {/* Bottom Sparkline and Subtext */}
            <div className="mt-4 flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-medium">{metric.subtext}</span>
              
              {/* Micro-sparkline SVG */}
              <div className="w-24 h-8 overflow-hidden">
                <svg className="w-full h-full" viewBox="0 0 160 30">
                  <path
                    d={metric.sparklinePath}
                    fill="none"
                    stroke={metric.strokeColor}
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
