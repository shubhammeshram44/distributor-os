"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import MetricCards from "@/components/MetricCards";
import RecentOrders from "@/components/RecentOrders";
import CollectionsDonut from "@/components/CollectionsDonut";
import LiveDeliveries from "@/components/LiveDeliveries";
import InventorySummary from "@/components/InventorySummary";
import ActivityFeed from "@/components/ActivityFeed";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useSalesOverview } from "@/hooks/useSalesOverview";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { ChevronDown, SlidersHorizontal, RefreshCw, CheckCircle2, AlertCircle, X } from "lucide-react";
import WhatsAppSimulator from "@/components/WhatsAppSimulator";
import WelcomeHero from "@/components/dashboard/WelcomeHero";
import GettingStartedStrip from "@/components/dashboard/GettingStartedStrip";
import QuickActionsGrid from "@/components/dashboard/QuickActionsGrid";
import AlertsNotificationsCard from "@/components/dashboard/AlertsNotificationsCard";
import TopProductsCard from "@/components/dashboard/TopProductsCard";
import TopCustomersCard from "@/components/dashboard/TopCustomersCard";
import OrderPipelineCard from "@/components/dashboard/OrderPipelineCard";
import AIInsightsCard from "@/components/dashboard/AIInsightsCard";

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

  const getFirstName = () => {
    const fullName: string | undefined = userProfile?.full_name;
    if (!fullName) return "";
    return fullName.trim().split(/\s+/)[0];
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

  const { data: salesOverview, isLoading: salesOverviewLoading } = useSalesOverview(isHydrating ? "" : tenantId);

  // Real, non-fabricated signals used across the new ROI widgets below.
  const [whatsAppOpenTrigger, setWhatsAppOpenTrigger] = useState(0);
  const handleNewOrder = () => setWhatsAppOpenTrigger((n) => n + 1);

  const hasProducts = (metrics?.total_skus_count ?? metrics?.total_skus ?? 0) > 0;
  const hasOrders = (metrics?.orders_count ?? 0) > 0;
  const hasConfirmedOrder = recentOrders.some((o) => o.status && !["Draft", "Pending"].includes(o.status));

  const pendingOrdersCount = salesOverview?.status_distribution?.Pending ?? 0;
  const lowStockCount = metrics?.low_stock_count ?? 0;
  const outOfStockCount = metrics?.out_of_stock_count ?? 0;
  const overdue60Count = metrics?.overdue_60_count ?? 0;
  const hasAlerts = pendingOrdersCount > 0 || lowStockCount > 0 || outOfStockCount > 0 || overdue60Count > 0;

  if (!tenantId || tenantId === "") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-dashDark-bg">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashDark-bg min-h-screen text-dashDark-text">
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
          hasAlerts={hasAlerts}
        />

        {/* 3. Dashboard Scrollable Content */}
        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {isHydrating ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3 bg-dashDark-card rounded-xl border border-dashDark-border h-[400px]">
              <div className="w-8 h-8 rounded-full border-4 border-dashDark-border border-t-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-dashDark-textMuted">Hydrating your workspace profile...</span>
            </div>
          ) : (
            <>
              {/* Dashboard Control Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-dashDark-text tracking-tight">Dashboard</h1>
                  <p className="text-xs text-dashDark-textMuted font-semibold mt-0.5">Real-time operational workflow management</p>
                </div>

                {/* Date Picker & Action Controls */}
                <div className="flex items-center gap-3">
                  {/* Unified Timeframe Selector */}
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-semibold text-dashDark-textMuted">Timeframe:</label>
                    <select
                      value={timeframe}
                      onChange={(e) => {
                        setTimeframe(e.target.value);
                        handleTimeframeChange(e.target.value);
                      }}
                      className="bg-dashDark-cardAlt border border-dashDark-border text-dashDark-text text-xs font-bold rounded-xl px-3 py-2 focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue transition-all cursor-pointer outline-none"
                    >
                      <option value="7days">Last 7 Days</option>
                      <option value="30days">Last 30 Days</option>
                      <option value="thisMonth">This Month</option>
                      <option value="custom">Custom Range</option>
                    </select>
                  </div>

                  {timeframe === "custom" && (
                    <div className="flex items-center gap-2 animate-fade-in">
                      <div className="flex items-center gap-1.5 bg-dashDark-cardAlt border border-dashDark-border rounded-lg px-2.5 py-1.5">
                        <span className="text-[10px] uppercase font-bold text-dashDark-textFaint">From</span>
                        <input
                          type="date"
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="text-xs font-semibold text-dashDark-textMuted bg-transparent focus:outline-none cursor-pointer"
                        />
                      </div>
                      <div className="flex items-center gap-1.5 bg-dashDark-cardAlt border border-dashDark-border rounded-lg px-2.5 py-1.5">
                        <span className="text-[10px] uppercase font-bold text-dashDark-textFaint">To</span>
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="text-xs font-semibold text-dashDark-textMuted bg-transparent focus:outline-none cursor-pointer"
                        />
                      </div>
                      {(startDate || endDate) && (
                        <button
                          onClick={() => {
                            setStartDate("");
                            setEndDate("");
                          }}
                          className="p-1.5 text-dashDark-textFaint hover:text-dashDark-text bg-dashDark-cardAlt border border-dashDark-border rounded-lg"
                          title="Clear date filters"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  )}

                  {/* Customize Layout Button */}
                  <button className="flex items-center gap-1.5 px-3 py-2 border border-dashDark-border bg-dashDark-cardAlt rounded-lg text-xs font-semibold text-dashDark-textMuted hover:bg-dashDark-card hover:text-dashDark-text transition-all">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-dashDark-textFaint" />
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

              {/* Welcome banner + primary New Order CTA (real order-creation entry point) */}
              <WelcomeHero firstName={getFirstName()} onNewOrder={handleNewOrder} />

              {/* Getting Started onboarding strip — every step is a real, verifiable signal */}
              <GettingStartedStrip
                activeTenantId={tenantId}
                hasProducts={hasProducts}
                hasOrders={hasOrders}
                hasConfirmedOrder={hasConfirmedOrder}
              />

              {/* A. Core Operational Metrics Row */}
              <MetricCards metrics={metrics} />

              {/* A2. Quick Actions + Alerts + Insights Row (new ROI-focused widgets) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="min-h-[220px]">
                  <QuickActionsGrid onNewOrder={handleNewOrder} />
                </div>
                <div className="min-h-[220px]">
                  <AlertsNotificationsCard
                    pendingOrdersCount={pendingOrdersCount}
                    lowStockCount={lowStockCount}
                    outOfStockCount={outOfStockCount}
                    overdue60Count={overdue60Count}
                  />
                </div>
                <div className="min-h-[220px]">
                  <AIInsightsCard
                    salesChange={metrics?.total_sales_change}
                    ordersChange={metrics?.orders_count_change}
                    collectionsChange={metrics?.outstanding_collections_change}
                    lowStockCount={lowStockCount}
                  />
                </div>
              </div>

              {/* A3. Top Products + Order Pipeline + Top Customers Row (new ROI-focused widgets) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="min-h-[260px]">
                  <TopProductsCard products={salesOverview?.top_moving_skus ?? []} isLoading={salesOverviewLoading} />
                </div>
                <div className="min-h-[260px]">
                  <OrderPipelineCard statusDistribution={salesOverview?.status_distribution ?? {}} />
                </div>
                <div className="min-h-[260px]">
                  <TopCustomersCard activeTenantId={tenantId} />
                </div>
              </div>

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

              {/* C. Bottom Operational Grid (Live Map, Stock Summary, Activity Feed) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="min-h-[300px]">
                  <LiveDeliveries viewAllHref="/dashboard/shipments" />
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
        externalOpenTrigger={whatsAppOpenTrigger}
      />

      {/* Sleek Floating Toast Notification */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-dashDark-card/95 backdrop-blur-md border border-dashDark-border shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-sm">
          {toast.type === "success" ? (
            <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle2 className="w-4.5 h-4.5" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-rose-500/10 flex items-center justify-center text-rose-400 shrink-0">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-dashDark-text">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-dashDark-textMuted font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            className="text-dashDark-textFaint hover:text-dashDark-text p-0.5 rounded-full hover:bg-dashDark-cardAlt transition-all shrink-0"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
