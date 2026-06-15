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

  // Sync profile and tenant from backend / localStorage
  useEffect(() => {
    const fetchProfileAndTenant = async () => {
      try {
        const storedTenant = localStorage.getItem("tenant_id");
        if (storedTenant) {
          setTenantId(storedTenant);
        }

        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${apiBase}/api/v1/auth/me`, {
          method: "GET",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          }
        });
        if (resp.ok) {
          const profileData = await resp.json();
          setUserProfile(profileData);
          
          // If no tenant is selected or in localStorage, default to user's assigned tenant
          if (!storedTenant && profileData.tenant?.id) {
            setTenantId(profileData.tenant.id);
            localStorage.setItem("tenant_id", profileData.tenant.id);
          }
        }
      } catch (err) {
        console.error("Failed to load authenticated user profile:", err);
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
    if (userProfile?.tenant?.id === tenantId) {
      return userProfile.tenant.name || "My Workspace";
    }
    switch (tenantId) {
      case "d3b07384-d113-4956-a5d2-64be7357c11d":
        return "S.V. Distributors";
      case "e1c08495-d224-4a67-b6e3-75cf8468d22e":
        return "Reliance Distribution";
      case "f2d095a6-e335-5b78-c7f4-86df9579e33f":
        return "Vikas Sales Corp";
      default:
        return "S.V. Distributors";
    }
  };

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

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
  } = useDashboardData(tenantId, startDate, endDate);

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

              {/* Date Filter Input Selectors */}
              <div className="flex items-center gap-2">
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

              {/* Customize Layout */}
              <button className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm">
                <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
                <span>Customize</span>
              </button>
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
