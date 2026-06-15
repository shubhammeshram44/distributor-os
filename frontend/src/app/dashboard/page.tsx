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
import { ChevronDown, SlidersHorizontal, RefreshCw, CheckCircle2, AlertCircle, X } from "lucide-react";
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
          credentials: "include", // Retain HttpOnly channel compatibility
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {}) // CRITICAL: Standard Bearer token authentication fallback
          }
        });

        // CRITICAL: Redirect to auth on 401 (expired/missing cookie)
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
          
          // If no tenant is selected or in localStorage, default to user's assigned tenant
          if (!storedTenant && profileData.tenant?.id) {
            setTenantId(profileData.tenant.id);
            localStorage.setItem("tenant_id", profileData.tenant.id);
          }
        }
      } catch (err) {
        // Network failure (backend unreachable) — redirect to auth
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

  // Get active tenant name
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

  // Absolute multi-tenant protection guard
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
              {error && (
                <button
                  onClick={refreshAll}
                  className="flex items-center gap-1.5 px-3 py-2 bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold rounded-lg hover:bg-rose-100 transition-all"
                  title={error}
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Reload Connection</span>
                </button>
              )}

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

            </div>
          </div>

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

          {/* C. Bottom Operational Grid (Live Map, Stock Summary, Activity Feed) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="relative border border-slate-100 rounded-2xl p-6 bg-white overflow-hidden min-h-[300px]">
              {/* Translucent Backdrop Blur */}
              <div className="absolute inset-0 bg-slate-50/60 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center text-center p-4">
                <span className="bg-blue-50 text-blue-700 text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full mb-2 shadow-sm border border-blue-100">
                  Coming Soon
                </span>
                <p className="text-xs font-bold text-slate-700">Real-Time Driver GPS Tracking</p>
                <p className="text-[11px] text-slate-400 mt-0.5 max-w-[200px]">Lightweight PWA integration with browser-native HTML5 location tracking is on the immediate horizon.</p>
              </div>

              {/* Keep underlying template or existing placeholder layout code intact beneath the overlay */}
              <div className="opacity-25 pointer-events-none">
                <LiveDeliveries viewAllHref="/dashboard/shipments" />
              </div>
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
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 backdrop-blur-md border border-slate-100 shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-w-sm">
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
