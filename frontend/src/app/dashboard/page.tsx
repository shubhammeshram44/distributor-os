"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import MetricCards from "@/components/MetricCards";
import CollectionsDonut from "@/components/CollectionsDonut";
// LiveDeliveries import removed 2026-06-28 — replaced by DemandGapCard in the bottom grid.
// The component file (LiveDeliveries.tsx) is preserved on disk for future use.
import InventorySummary from "@/components/InventorySummary";
import DemandGapCard from "@/components/DemandGapCard";
import CashFlowForecastCard from "@/components/CashFlowForecastCard";
// ActivityFeed replaced with simple link (see bottom of dashboard layout)
import OnboardingChecklist from "@/components/OnboardingChecklist";
import { useDashboardData, DashboardMetrics } from "@/hooks/useDashboardData";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { formatDateTime } from "@/utils/datetime";
import PlaceOrderModal from "@/components/PlaceOrderModal";
import RevenueTrendChart from "@/components/RevenueTrendChart";
import { BarChart3, PackagePlus, Plus, ReceiptText, RefreshCw, UserPlus } from "lucide-react";


export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [tenantId, setTenantId] = useState("");
  const [userProfile, setUserProfile] = useState<any>(null);
  const [isHydrating, setIsHydrating] = useState(true);
  const [waStatus, setWaStatus] = useState<{
    whatsapp_connected: boolean;
    has_whatsapp: boolean;
    disconnected_at: string | null;
    disconnect_reason: string | null;
  } | null>(null);
  const [waBannerDismissed, setWaBannerDismissed] = useState(false);
  const [creditRisk, setCreditRisk] = useState<{
    alerts: Array<{
      customer_id: string;
      customer_name: string;
      outstanding: number;
      credit_utilisation_pct: number;
      overdue_days: number;
      risk_level: "high_risk" | "caution";
    }>;
    total_at_risk_count: number;
    total_at_risk_amount: number;
  } | null>(null);

  const [decisionFocus, setDecisionFocus] = useState<{
    decisions: Array<{
      type: string;
      priority: number;
      icon: string;
      headline: string;
      detail: string;
      amount_at_stake: number;
      action_label: string;
      action_url: string;
    }>;
    all_clear: boolean;
    generated_at: string;
  } | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(true);

  const [healthScore, setHealthScore] = useState<{
    has_sufficient_data: boolean;
    score: number;
    band: string;
    band_label: string;
    band_color: string;
    trend: string;
    trend_points: number;
    primary_insight: string;
    signals: {
      collections: { score: number; max: number; status: string; total_outstanding: number; overdue_30d: number; overdue_ratio_pct: number; };
      sales: { score: number; max: number; growth_pct: number; status: string; this_week_revenue: number; last_week_revenue: number; };
      recovery: { score: number; max: number; avg_days_to_pay: number; status: string; };
      inventory: { score: number; max: number; stockout_count: number; total_products: number; status: string; };
      fulfillment: { score: number; max: number; fulfillment_rate_pct: number; status: string; };
    };
    confirmed_orders?: number;
    days_of_data?: number;
  } | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthExpanded, setHealthExpanded] = useState(false);
  const [isPlaceOrderOpen, setIsPlaceOrderOpen] = useState(false);


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

  const getTenantName = () => {
    if (userProfile?.tenant?.name) {
      return userProfile.tenant.name;
    }
    return "Loading Workspace...";
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
    refreshAll: originalRefreshAll,
    error
  } = useDashboardData(isHydrating ? "" : tenantId, undefined, undefined);

  const [orders, setOrders] = useState<any[]>([]);

  const fetchOrders = useCallback(async () => {
    if (!tenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    try {
      const res = await fetch(`${apiBase}/api/v1/orders?tenant_id=${tenantId}&limit=100`);
      if (res.ok) {
        const data = await res.json();
        setOrders(data.items || []);
      }
    } catch (e) {
      console.error("Failed to fetch orders:", e);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const fetchCreditRisk = useCallback(async () => {
    if (!tenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    try {
      const creditRes = await fetch(
        `${apiBase}/api/v1/dashboard/credit-risk-alerts?tenant_id=${tenantId}`
      );
      const creditData = await creditRes.json();
      setCreditRisk(creditData);
    } catch (e) {
      console.error("Failed to fetch credit risk alerts:", e);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchCreditRisk();
  }, [fetchCreditRisk]);

  const fetchDecisionFocus = useCallback(async () => {
    if (!tenantId) return;
    setDecisionLoading(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    try {
      const decisionRes = await fetch(
        `${apiBase}/api/v1/dashboard/decision-focus?tenant_id=${tenantId}`
      );
      const decisionData = await decisionRes.json();
      setDecisionFocus(decisionData);
    } catch (e) {
      console.error("Failed to fetch decision focus:", e);
    } finally {
      setDecisionLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchDecisionFocus();
  }, [fetchDecisionFocus]);

  const fetchHealthScore = useCallback(async () => {
    if (!tenantId) return;
    setHealthLoading(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    try {
      const healthRes = await fetch(
        `${apiBase}/api/v1/dashboard/business-health-score?tenant_id=${tenantId}`
      );
      const healthData = await healthRes.json();
      setHealthScore(healthData);
    } catch (e) {
      console.error("Failed to fetch business health score:", e);
    } finally {
      setHealthLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchHealthScore();
  }, [fetchHealthScore]);

  const refreshAll = () => {
    originalRefreshAll();
    fetchCreditRisk();
    fetchDecisionFocus();
    fetchHealthScore();
    fetchOrders();
  };

  // Poll connection status every 60 seconds
  useEffect(() => {
    if (!tenantId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const check = async () => {
      try {
        // First get tenant connection info
        const res = await fetch(
          `${apiBase}/api/v1/tenant/connection-status?tenant_id=${tenantId}`
        );
        const data = await res.json();

        // If tenant has WhatsApp configured, verify real-time status
        if (data.has_whatsapp && data.connection_status !== "unknown") {
          try {
            const statusRes = await fetch(
              `${apiBase}/api/v1/evolution/status?instance_name=dist-${tenantId.substring(0, 8)}&tenant_id=${tenantId}`
            );
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              // Override DB status with real-time status
              data.whatsapp_connected = statusData.connected === true;
            }
          } catch (e) {
            // If evolution API unreachable, trust DB status
          }
        }

        setWaStatus(data);
        // Reset dismissed state if reconnected
        if (data.whatsapp_connected) setWaBannerDismissed(false);
      } catch (e) { }
    };
    check();
    const interval = setInterval(check, 60000);
    return () => clearInterval(interval);
  }, [tenantId]);

  if (!tenantId || tenantId === "") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-dashboard-inset">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800 dark:text-slate-100">
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
            <div className="flex flex-col items-center justify-center py-32 gap-3 bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm h-[400px]">
              <div className="w-8 h-8 rounded-full border-4 border-slate-200 dark:border-white/10 border-t-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Setting up your workspace...</span>
            </div>
          ) : (
            <>
              {/* Dashboard Control Header */}
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight">Business command center</h1>
                  <p className="text-xs text-slate-400 font-semibold mt-0.5">Your current performance, priorities, and next actions in one place.</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={refreshAll}
                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-dashboard-border bg-white px-3 text-xs font-semibold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 dark:hover:bg-white/5 dark:bg-dashboard-card dark:text-slate-300 dark:hover:bg-white/5"
                    title="Refresh dashboard data"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsPlaceOrderOpen(true)}
                    className="inline-flex h-9 items-center gap-2 rounded-lg bg-emerald-600 px-3 text-xs font-bold text-white shadow-sm transition-colors hover:bg-emerald-700"
                  >
                    <Plus className="h-4 w-4" />
                    New order
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

              {/* WhatsApp Disconnection Banner */}
              {waStatus &&
                waStatus.has_whatsapp &&
                !waStatus.whatsapp_connected &&
                !waBannerDismissed && (
                  <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🔴</span>
                      <div>
                        <span className="text-red-700 dark:text-red-400 font-semibold text-sm">
                          WhatsApp Disconnected
                        </span>
                        <span className="text-red-600 dark:text-red-400 text-xs ml-2">
                          Orders are not being received
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <a
                        href="/dashboard/settings/integrations"
                        className="px-3 py-1.5 bg-red-600 text-white text-xs font-semibold rounded-lg hover:bg-red-700"
                      >
                        Reconnect Now →
                      </a>
                      <button
                        onClick={() => setWaBannerDismissed(true)}
                        className="text-red-400 hover:text-red-600 text-lg leading-none"
                        title="Dismiss"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                )}

              {/* Getting Started checklist — only renders for a brand-new,
                  unfinished workspace; disappears once dismissed or complete. */}
              <OnboardingChecklist activeTenantId={tenantId} />

              {/* The KPI strip turns raw operational data into momentum at a glance. */}
              <MetricCards metrics={metrics} />

              {/* High-frequency workflows stay visible without competing with the primary order action. */}
              <section aria-label="Quick actions" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <a
                  href="/dashboard/products"
                  className="group flex min-h-20 items-center gap-3 rounded-lg border border-dashboard-border bg-white px-3 shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50/50 dark:bg-dashboard-card dark:hover:border-blue-500/30 dark:hover:bg-blue-500/5"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400"><PackagePlus className="h-4 w-4" /></span>
                  <span className="min-w-0 text-left"><span className="block text-xs font-bold text-slate-700 dark:text-slate-200">Add product</span><span className="mt-0.5 block text-[10px] font-medium text-slate-400">Update catalog</span></span>
                </a>
                <a
                  href="/dashboard/customers"
                  className="group flex min-h-20 items-center gap-3 rounded-lg border border-dashboard-border bg-white px-3 shadow-sm transition-colors hover:border-violet-200 hover:bg-violet-50/50 dark:bg-dashboard-card dark:hover:border-violet-500/30 dark:hover:bg-violet-500/5"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400"><UserPlus className="h-4 w-4" /></span>
                  <span className="min-w-0 text-left"><span className="block text-xs font-bold text-slate-700 dark:text-slate-200">Add customer</span><span className="mt-0.5 block text-[10px] font-medium text-slate-400">Grow your network</span></span>
                </a>
                <a
                  href="/dashboard/collections"
                  className="group flex min-h-20 items-center gap-3 rounded-lg border border-dashboard-border bg-white px-3 shadow-sm transition-colors hover:border-amber-200 hover:bg-amber-50/50 dark:bg-dashboard-card dark:hover:border-amber-500/30 dark:hover:bg-amber-500/5"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400"><ReceiptText className="h-4 w-4" /></span>
                  <span className="min-w-0 text-left"><span className="block text-xs font-bold text-slate-700 dark:text-slate-200">Record payment</span><span className="mt-0.5 block text-[10px] font-medium text-slate-400">Keep receivables current</span></span>
                </a>
                <a
                  href="/dashboard/reports"
                  className="group flex min-h-20 items-center gap-3 rounded-lg border border-dashboard-border bg-white px-3 shadow-sm transition-colors hover:border-emerald-200 hover:bg-emerald-50/50 dark:bg-dashboard-card dark:hover:border-emerald-500/30 dark:hover:bg-emerald-500/5"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"><BarChart3 className="h-4 w-4" /></span>
                  <span className="min-w-0 text-left"><span className="block text-xs font-bold text-slate-700 dark:text-slate-200">View reports</span><span className="mt-0.5 block text-[10px] font-medium text-slate-400">Review performance</span></span>
                </a>
              </section>

              {/* Business Health Score */}
              {/* Business Health Score - Full Width */}
              {!healthLoading && healthScore?.has_sufficient_data && (
                <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 shadow-sm mb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="flex items-center gap-5">
                      {/* Circular score */}
                      <div className="relative w-16 h-16 flex-shrink-0">
                        <svg className="w-16 h-16 -rotate-90" viewBox="0 0 56 56">
                          <circle cx="28" cy="28" r="24" fill="none" stroke="#e2e8f0" strokeWidth="4.5" />
                          <circle
                            cx="28" cy="28" r="24"
                            fill="none"
                            stroke={
                              healthScore.band === "excellent" ? "#10b981" :
                                healthScore.band === "good" ? "#f59e0b" :
                                  healthScore.band === "attention" ? "#f97316" : "#ef4444"
                            }
                            strokeWidth="4.5"
                            strokeDasharray={`${(healthScore.score / 100) * 150.8} 150.8`}
                            strokeLinecap="round"
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-base font-bold text-slate-800 dark:text-slate-100">
                            {healthScore.score}
                          </span>
                        </div>
                      </div>

                      {/* Score details */}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                            Business Health
                          </span>
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${healthScore.band === "excellent" ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" :
                            healthScore.band === "good" ? "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400" :
                              healthScore.band === "attention" ? "bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400" :
                                "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400"
                            }`}>
                            {healthScore.band_label}
                          </span>
                          {/* Trend */}
                          <span className={`text-xs font-medium ${healthScore.trend === "up" ? "text-emerald-600 dark:text-emerald-400" :
                            healthScore.trend === "down" ? "text-red-500" :
                              "text-slate-400"
                            }`}>
                            {healthScore.trend === "up" ? "↑" :
                              healthScore.trend === "down" ? "↓" : "→"}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                          {healthScore.primary_insight}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setHealthExpanded((expanded) => !expanded)}
                      className="self-start rounded-lg border border-dashboard-border px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/5 sm:self-auto"
                    >
                      {healthExpanded ? "Hide drivers" : "View drivers"}
                    </button>
                  </div>
                  {healthExpanded && (
                    <div className="mt-5 grid grid-cols-1 gap-2 border-t border-slate-100 pt-4 dark:border-white/5 sm:grid-cols-2 lg:grid-cols-5">
                      {[
                        ["Collections", healthScore.signals.collections],
                        ["Sales", healthScore.signals.sales],
                        ["Recovery", healthScore.signals.recovery],
                        ["Inventory", healthScore.signals.inventory],
                        ["Fulfillment", healthScore.signals.fulfillment],
                      ].map(([label, signal]) => {
                        const driver = signal as { score: number; max: number; status: string };
                        const color = driver.status === "good" ? "bg-emerald-500" : driver.status === "attention" ? "bg-amber-500" : "bg-red-500";
                        return (
                          <div key={label as string} className="rounded-lg bg-slate-50 p-3 dark:bg-dashboard-inset">
                            <div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-slate-600 dark:text-slate-300">{label as string}</span><span className="text-[10px] font-bold text-slate-400">{driver.score}/{driver.max}</span></div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10"><div className={`h-full rounded-full ${color}`} style={{ width: `${(driver.score / driver.max) * 100}%` }} /></div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Not enough data state */}
              {!healthLoading && healthScore && !healthScore.has_sufficient_data && (
                <div className="bg-slate-50 dark:bg-dashboard-inset rounded-xl border border-slate-200 dark:border-white/10 p-6 flex items-center gap-3 mb-6">
                  <span className="text-xl">📊</span>
                  <div>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">Business Health Score</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Available after 7 days and 5 confirmed orders.
                      {healthScore.confirmed_orders !== undefined && healthScore.confirmed_orders > 0 && ` ${healthScore.confirmed_orders}/5 orders so far.`}
                    </p>
                  </div>
                </div>
              )}

              {/* ⚡ Decision Focus Card */}
              <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 overflow-hidden mb-6 shadow-sm">
                {/* Header */}
                <div className="px-6 py-5 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                      ⚡ Focus for the Next 15 Minutes
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Based on your current orders, collections, and inventory
                    </p>
                  </div>
                  {decisionFocus?.generated_at && (
                    <span className="text-xs text-slate-400">
                      Updated {formatDateTime(decisionFocus.generated_at, "relative")}
                    </span>
                  )}
                </div>

                {/* Loading skeleton */}
                {decisionLoading && (
                  <div className="p-6 space-y-3">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="h-16 bg-slate-100 dark:bg-white/5 rounded-lg animate-pulse" />
                    ))}
                  </div>
                )}

                {/* All clear state */}
                {!decisionLoading && decisionFocus?.all_clear && (
                  <div className="p-8 text-center">
                    <div className="text-3xl mb-2">✅</div>
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">All caught up!</p>
                    <p className="text-xs text-slate-400 mt-1">
                      No pending actions right now. Your business is running smoothly.
                    </p>
                  </div>
                )}

                {/* Decision items */}
                {!decisionLoading && decisionFocus && !decisionFocus.all_clear && (
                  <div className="divide-y divide-slate-50">
                    {decisionFocus.decisions.map((decision, idx) => (
                      <div
                        key={decision.type}
                        className={`flex items-start gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors ${idx === 0 ? "bg-red-50/30 dark:bg-red-500/5" : ""
                          }`}
                      >
                        {/* Icon */}
                        <span className="text-xl flex-shrink-0 mt-0.5">{decision.icon}</span>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                            {decision.headline}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
                            {decision.detail}
                          </p>
                        </div>

                        {/* Action button */}
                        <a
                          href={decision.action_url}
                          className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${idx === 0
                            ? "bg-red-600 text-white hover:bg-red-700"
                            : "bg-slate-100 dark:bg-white/5 text-slate-700 dark:text-slate-300 hover:bg-slate-200"
                            }`}
                        >
                          {decision.action_label} →
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Row 4: Operational Controls (Col A: Collections + Credit Risk | Col B: Orders Status | Col C: Health Details) */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6 mb-6">
                {/* Column A (lg:col-span-5): Credit Risk Alerts */}
                <div className="md:col-span-1 lg:col-span-5">
                  {/* Credit Risk Alerts List */}
                  {creditRisk && creditRisk.alerts.length > 0 ? (
                    <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 shadow-sm h-full flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                              ⚠️ Credit Risk Alerts
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                              {creditRisk.total_at_risk_count} customers ·
                              ₹{creditRisk.total_at_risk_amount.toLocaleString("en-IN")} at risk
                            </p>
                          </div>
                          <a href="/dashboard/customers"
                            className="text-xs text-emerald-600 dark:text-emerald-400 font-medium hover:underline">
                            View All →
                          </a>
                        </div>

                        {/* Risk summary bar */}
                        <div className="flex gap-3 mb-4 p-3 bg-slate-50 dark:bg-dashboard-inset rounded-lg">
                          <div className="flex-1 text-center">
                            <div className="text-lg font-bold text-red-600 dark:text-red-400">
                              {creditRisk.alerts.filter(a => a.risk_level === "high_risk").length}
                            </div>
                            <div className="text-xs text-slate-500 dark:text-slate-400">🔴 High Risk</div>
                          </div>
                          <div className="w-px bg-slate-200 dark:bg-white/10" />
                          <div className="flex-1 text-center">
                            <div className="text-lg font-bold text-amber-500">
                              {creditRisk.alerts.filter(a => a.risk_level === "caution").length}
                            </div>
                            <div className="text-xs text-slate-500 dark:text-slate-400">🟡 Caution</div>
                          </div>
                          <div className="w-px bg-slate-200 dark:bg-white/10" />
                          <div className="flex-1 text-center">
                            <div className="text-lg font-bold text-slate-700 dark:text-slate-300">
                              ₹{(creditRisk.total_at_risk_amount / 1000).toFixed(1)}K
                            </div>
                            <div className="text-xs text-slate-500 dark:text-slate-400">Total Due</div>
                          </div>
                        </div>

                        {/* Customer list */}
                        <div className="space-y-2">
                          {creditRisk.alerts.map((alert) => (
                            <div
                              key={alert.customer_id}
                              className={`flex items-center gap-3 p-3 rounded-lg border-l-4 ${alert.risk_level === "high_risk"
                                ? "bg-red-50 dark:bg-red-500/10 border-red-400"
                                : "bg-amber-50 dark:bg-amber-500/10 border-amber-400"
                                }`}
                            >
                              <span className="text-base flex-shrink-0">
                                {alert.risk_level === "high_risk" ? "🔴" : "🟡"}
                              </span>

                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                                  {alert.customer_name}
                                </p>

                                <div className="flex items-center gap-2 mt-1">
                                  <div className="flex-1 bg-slate-200 dark:bg-white/10 rounded-full h-1.5">
                                    <div
                                      className={`h-1.5 rounded-full ${alert.risk_level === "high_risk"
                                        ? "bg-red-400"
                                        : "bg-amber-400"
                                        }`}
                                      style={{
                                        width: `${Math.min(100, (alert.overdue_days / 90) * 100)}%`
                                      }}
                                    />
                                  </div>
                                  <span className="text-xs text-slate-500 dark:text-slate-400 flex-shrink-0">
                                    {alert.overdue_days}d overdue
                                  </span>
                                </div>
                              </div>

                              <div className="text-right flex-shrink-0">
                                <p className={`text-xs font-bold ${alert.risk_level === "high_risk"
                                  ? "text-red-600 dark:text-red-400"
                                  : "text-amber-600 dark:text-amber-400"
                                  }`}>
                                  ₹{alert.outstanding.toLocaleString("en-IN")}
                                </p>
                                <p className="text-xs text-slate-400">
                                  {alert.credit_utilisation_pct}% used
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>

                        {creditRisk.total_at_risk_count > 5 && (
                          <p className="text-xs text-slate-400 mt-3 text-center">
                            +{creditRisk.total_at_risk_count - 5} more customers need attention
                          </p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 shadow-sm h-full flex flex-col justify-center items-center text-center min-h-[300px]">
                      <span className="text-3xl mb-3">🛡️</span>
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No Credit Risks</p>
                      <p className="text-xs text-slate-400 mt-1.5 max-w-[240px] leading-relaxed">
                        All customers are within their credit limits and payment terms.
                      </p>
                    </div>
                  )}
                </div>

                {/* Column B (lg:col-span-4): Orders Status (Orders Intelligence) */}
                <div className="md:col-span-1 lg:col-span-4">
                  <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 flex flex-col justify-between h-full shadow-sm">
                    <div className="flex-1 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-5">
                        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">📦 Orders Status</h3>
                        <a href="/dashboard/orders" className="text-xs text-emerald-600 dark:text-emerald-400 font-medium hover:underline">
                          View all →
                        </a>
                      </div>
                      <div className="space-y-4 flex-1 flex flex-col justify-around">
                        {[
                          {
                            label: "Pending confirmation",
                            count: orders?.filter((o: any) => o.status === "Pending").length || 0,
                            color: "text-amber-600 dark:text-amber-400",
                            bg: "bg-amber-50 dark:bg-amber-500/10",
                            url: "/dashboard/orders?status=Pending",
                            suffix: orders?.filter((o: any) => o.status === "Pending").length > 0 ? "→ Confirm now" : "→ All clear"
                          },
                          {
                            label: "Needs review",
                            count: orders?.filter((o: any) => o.status === "Needs Review").length || 0,
                            color: "text-red-600 dark:text-red-400",
                            bg: "bg-red-50 dark:bg-red-500/10",
                            url: "/dashboard/orders?status=Needs+Review",
                            suffix: "→ Action needed"
                          },
                          {
                            label: "Awaiting stock",
                            count: orders?.filter((o: any) => o.status === "Awaiting Stock").length || 0,
                            color: "text-slate-500 dark:text-slate-400",
                            bg: "bg-slate-50 dark:bg-dashboard-inset",
                            url: "/dashboard/orders?status=Awaiting+Stock",
                            suffix: "→ Restock needed"
                          },
                          {
                            label: "Dispatched today",
                            count: orders?.filter((o: any) => o.status === "Dispatched").length || 0,
                            color: "text-blue-600 dark:text-blue-400",
                            bg: "bg-blue-50 dark:bg-blue-500/10",
                            url: "/dashboard/shipments",
                            suffix: "→ In transit"
                          }
                        ].map(item => (
                          <a
                            key={item.label}
                            href={item.url}
                            className={`flex items-center justify-between py-3.5 px-4 rounded-lg ${item.bg} hover:opacity-80 transition-opacity border border-slate-100/50 dark:border-white/[0.08]`}
                          >
                            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">{item.label}</span>
                            <div className="flex items-center gap-2">
                              <span className={`text-sm font-bold ${item.color}`}>{item.count}</span>
                              {item.count > 0 && (
                                <span className={`text-xs font-bold ${item.color}`}>{item.suffix}</span>
                              )}
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Column C (lg:col-span-3): Business Health details */}
                <div className="md:col-span-2 lg:col-span-3">
                  <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 flex flex-col justify-between h-full shadow-sm">
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">📊 Health Details</h3>
                      </div>
                      {healthLoading ? (
                        <div className="space-y-3">
                          {[1, 2, 3].map(i => (
                            <div key={i} className="h-10 bg-slate-100 dark:bg-white/5 rounded-lg animate-pulse" />
                          ))}
                        </div>
                      ) : healthScore?.has_sufficient_data ? (
                        <div className="space-y-4">
                          {[
                            {
                              key: "collections",
                              label: "Collections",
                              detail: `${healthScore.signals.collections.score}/${healthScore.signals.collections.max} pts`
                            },
                            {
                              key: "sales",
                              label: "Sales Momentum",
                              detail: `${healthScore.signals.sales.growth_pct > 0 ? "+" : ""}${healthScore.signals.sales.growth_pct}% vs last week`
                            },
                            {
                              key: "recovery",
                              label: "Payment Recovery",
                              detail: `Avg ${healthScore.signals.recovery.avg_days_to_pay} days to collect`
                            },
                            {
                              key: "inventory",
                              label: "Inventory",
                              detail: `${healthScore.signals.inventory.stockout_count} products out of stock`
                            },
                            {
                              key: "fulfillment",
                              label: "Order Fulfillment",
                              detail: `${healthScore.signals.fulfillment.fulfillment_rate_pct}% fully fulfilled`
                            }
                          ].map(({ key, label, detail }) => {
                            const signal = healthScore.signals[key as keyof typeof healthScore.signals];
                            return (
                              <div key={key} className="flex items-center gap-3">
                                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${signal.status === "good" ? "bg-emerald-400" :
                                  signal.status === "attention" ? "bg-amber-400" :
                                    "bg-red-400"
                                  }`} />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 truncate mr-2">{label}</span>
                                    <span className="text-[10px] font-semibold text-slate-400 shrink-0">{detail}</span>
                                  </div>
                                  <div className="mt-1 h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden">
                                    <div
                                      className={`h-full rounded-full ${signal.status === "good" ? "bg-emerald-400" :
                                        signal.status === "attention" ? "bg-amber-400" :
                                          "bg-red-400"
                                        }`}
                                      style={{
                                        width: `${(signal.score / signal.max) * 100}%`
                                      }}
                                    />
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="text-xs text-slate-400 flex items-center justify-center h-48 border border-dashed border-slate-100 dark:border-white/5 rounded-lg">
                          Metrics details unavailable
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Row 4.5: Revenue Trend — same data source as the full Reports page */}
              <div className="h-[320px]">
                <RevenueTrendChart activeTenantId={tenantId} />
              </div>

              {/* Row 5: Collections aging donut | Demand Gap | Inventory Summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
                <div className="flex flex-col h-full">
                  <CollectionsDonut
                    data={donutData}
                    viewReportHref="/dashboard/collections"
                    overdue60Count={metrics?.overdue_60_count}
                  />
                </div>
                <div className="flex flex-col h-full">
                  <DemandGapCard activeTenantId={tenantId} />
                </div>
                <div className="flex flex-col h-full">
                  <InventorySummary data={metrics || undefined} />
                </div>
              </div>

              {/* Row 5.5: Cash Flow Forecast */}
              <div className="grid grid-cols-1 gap-6">
                <CashFlowForecastCard activeTenantId={tenantId} />
              </div>

              {/* Row 6: Recent Activity Footer (Hidden for now) */}
              {/*
              {activities && activities.length > 0 && (
                <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6 mt-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Recent Activity
                    </h3>
                    <a
                      href="/dashboard/reports"
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 transition-colors font-semibold"
                    >
                      View all activity →
                    </a>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                    {activities.slice(0, 5).map((act: any, idx: number) => (
                      <div key={idx} className="flex items-center gap-3 text-xs bg-slate-50 dark:bg-dashboard-inset rounded-lg p-3">
                        <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-white/5 flex items-center justify-center text-sm shrink-0">
                          {act.type === "order" ? "🛒" : act.type === "payment" ? "💸" : "📦"}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-800 dark:text-slate-100 truncate">{act.title}</p>
                          <p className="text-slate-400 text-[10px] mt-0.5">{act.timestamp || "Just now"}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              */}
            </>
          )}
        </main>
        <PlaceOrderModal
          activeTenantId={tenantId}
          isOpen={isPlaceOrderOpen}
          onClose={() => setIsPlaceOrderOpen(false)}
          onSuccess={refreshAll}
        />
      </div>
    </div>
  );
}


