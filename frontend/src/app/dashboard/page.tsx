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
import { ChevronDown, SlidersHorizontal, RefreshCw, CheckCircle2, AlertCircle, X, Inbox } from "lucide-react";
import WhatsAppSimulator from "@/components/WhatsAppSimulator";

// Reusable micro-component to protect child components when data arrays are empty
const InlineCardEmptyState = ({ title, description }: { title: string; description: string }) => (
  <div className="flex flex-col items-center justify-center h-full w-full bg-white rounded-xl p-6 text-center border border-slate-100">
    <div className="w-9 h-9 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 mb-2 border border-slate-100">
      <Inbox className="w-4 h-4" />
    </div>
    <h4 className="text-xs font-bold text-slate-700">{title}</h4>
    <p className="text-[11px] text-slate-400 max-w-[220px] mt-1 leading-normal">{description}</p>
  </div>
);

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
    error,
    isLoading
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
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        <DashboardHeader
          activeTenantId={tenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
          userProfile={userProfile}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {isHydrating ? (
            <div className="flex flex-col items-center justify-center py-32 gap-3 bg-white rounded-xl border border-dashboard-border shadow-sm h-[400px]">
              <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500">Hydrating your workspace profile...</span>
            </div>
          ) : (
            <>
              {/* Controls and Header Remain Unaltered and Viewable */}
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-slate-800 tracking-tight">Dashboard</h1>
                  <p className="text-xs text-slate-400 font-semibold mt-0.5">Real-time operational workflow management</p>
                </div>
                
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
                    </div>
                  )}
                </div>
              </div>

              {/* A. Core Operational Metrics Row - Displays zero states cleanly */}
              <MetricCards metrics={metrics} />

              {/* B. Split Middle Pane - Row 2 */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                
                {/* Left Col: Recent Orders Card Frame */}
                <div className="lg:col-span-3 h-[340px]">
                  {isLoading ? (
                    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full justify-between">
                      <div className="h-6 bg-slate-100 rounded animate-pulse w-32" />
                      <div className="flex-1 space-y-4 my-2">
                        <div className="h-5 bg-slate-100 rounded w-full animate-pulse" />
                        <div className="h-5 bg-slate-50 rounded w-full animate-pulse" />
                      </div>
                    </div>
                  ) : !recentOrders || recentOrders.length === 0 ? (
                    <InlineCardEmptyState 
                      title="No Recent Orders Found" 
                      description="WhatsApp incoming order receipts or structured catalog checkout text pipelines haven't logged entries yet."
                    />
                  ) : (
                    <RecentOrders
                      orders={recentOrders}
                      fetchOrderDetails={fetchOrderDetails}
                      selectedOrderDetails={selectedOrderDetails}
                      loadingDetails={loadingDetails}
                      closeDetails={closeDetails}
                      onSuccess={(msg) => { showToast(msg, "success"); refreshAll(); }}
                      onError={(msg) => showToast(msg, "error")}
                      activeTenantId={tenantId}
                      viewAllHref="/dashboard/orders"
                    />
                  )}
                </div>

                {/* Right Col: Collections Donut Card Frame */}
                <div className="lg:col-span-2 h-[340px]">
                  {isLoading ? (
                    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full justify-between">
                      <div className="h-6 bg-slate-100 rounded animate-pulse w-40" />
                      <div className="w-28 h-28 rounded-full border-8 border-slate-100 mx-auto animate-pulse" />
                    </div>
                  ) : !donutData || donutData.length === 0 ? (
                    <InlineCardEmptyState 
                      title="No Outstanding Balance Records" 
                      description="Payment aging charts ledger data splits will construct once ledger invoices populate outstanding summaries."
                    />
                  ) : (
                    <CollectionsDonut
                      data={donutData}
                      viewReportHref="/dashboard/collections"
                      overdue60Count={metrics?.overdue_60_count}
                    />
                  )}
                </div>
              </div>

              {/* C. Operations Row 3 */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                <div className="lg:col-span-3 h-[280px]">
                  {isLoading ? (
                    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full justify-between">
                      <div className="h-4 bg-slate-100 rounded w-24 animate-pulse" />
                    </div>
                  ) : !metrics ? (
                    <InlineCardEmptyState 
                      title="Inventory Analytics Unavailable" 
                      description="Connect a read-only database tracking anchor or ERP integration node to read live ledger distributions."
                    />
                  ) : (
                    <InventorySummary data={metrics} />
                  )}
                </div>

                {/* Coming Soon Feature Card Block Frame */}
                <div className="lg:col-span-2 relative border border-slate-100 rounded-2xl p-6 bg-white overflow-hidden h-[280px]">
                  <div className="absolute inset-0 bg-slate-50/60 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center text-center p-4">
                    <span className="bg-blue-50 text-blue-700 text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full mb-2 shadow-sm border border-blue-100">
                      Coming Soon
                    </span>
                    <p className="text-xs font-bold text-slate-700">Real-Time Driver GPS Tracking</p>
                    <p className="text-[11px] text-slate-400 mt-0.5 max-w-[200px]">Lightweight PWA driver location tracking rails are under development.</p>
                  </div>
                  <div className="opacity-25 pointer-events-none h-full">
                    <LiveDeliveries viewAllHref="/dashboard/shipments" />
                  </div>
                </div>
              </div>

              {/* D. Audit Log Row 4 */}
              <div className="w-full">
                {isLoading ? (
                  <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm">
                    <div className="h-5 bg-slate-100 rounded w-full animate-pulse" />
                  </div>
                ) : !activities || activities.length === 0 ? (
                  <div className="bg-white border border-slate-100 rounded-xl p-8 text-center text-xs font-semibold text-slate-400">
                    No active internal webhook system audit logging items mapped yet.
                  </div>
                ) : (
                  <ActivityFeed activities={activities} viewAllHref="/dashboard/reports" />
                )}
              </div>
            </>
          )}
        </main>
      </div>

      <WhatsAppSimulator activeTenantId={tenantId} onSuccess={refreshAll} />

      {/* Floating System Toast Alerts */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 backdrop-blur-md border border-slate-100 shadow-2xl px-4 py-3.5 rounded-xl pointer-events-auto max-w-sm">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-slate-800">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-slate-500 font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button onClick={() => setToast(prev => ({ ...prev, show: false }))} className="text-slate-400 hover:text-slate-600">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
