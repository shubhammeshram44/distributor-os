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

  // Determine if backend analytical values are functionally empty
  const hasNoData = 
    !isLoading && 
    (!recentOrders || recentOrders.length === 0) && 
    (!activities || activities.length === 0);

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
              {/* Dashboard Control Header */}
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

              {/* DYNAMIC VIEW INTERCEPTOR: Handle Empty State Explicitly */}
              {hasNoData ? (
                <div className="flex flex-col items-center justify-center bg-white border border-dashed border-slate-200 rounded-2xl p-16 text-center shadow-sm min-h-[450px] w-full">
                  <div className="w-12 h-12 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 mb-4 border border-slate-100">
                    <Inbox className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-800">No Ingested Data Streams</h3>
                  <p className="text-xs text-slate-400 max-w-sm mt-1.5 leading-relaxed">
                    This workspace environment is configured correctly, but hasn't received transaction details yet. Use the WhatsApp Simulator panel to ingest sample audio entries or text logs.
                  </p>
                </div>
              ) : (
                <>
                  {/* A. Core Operational Metrics Row */}
                  <MetricCards metrics={metrics} />

                  {/* B. Split Middle Pane - Row 2 */}
                  <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                    <div className="lg:col-span-3 h-[340px]">
                      {isLoading ? (
                        <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full justify-between">
                          <div className="flex items-center justify-between pb-4 border-b border-dashboard-border mb-4">
                            <div className="h-6 bg-slate-100 rounded animate-pulse w-32" />
                            <div className="h-4 bg-slate-100 rounded animate-pulse w-16" />
                          </div>
                          <div className="flex-1 space-y-4 my-2">
                            <div className="h-5 bg-slate-100 rounded w-full animate-pulse" />
                            <div className="h-5 bg-slate-50 rounded w-full animate-pulse" />
                            <div className="h-5 bg-slate-50 rounded w-full animate-pulse" />
                          </div>
                        </div>
                      ) : (
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
                      )}
                    </div>

                    <div className="lg:col-span-2 h-[340px]">
                      {isLoading ? (
                        <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full justify-between">
                          <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
                            <div className="h-6 bg-slate-100 rounded animate-pulse w-40" />
                            <div className="h-4 bg-slate-100 rounded animate-pulse w-16" />
                          </div>
                          <div className="flex flex-col sm:flex-row lg:flex-col xl:flex-row items-center justify-between gap-4 py-1 flex-1">
                            <div className="relative w-36 h-36 flex items-center justify-center">
                              <div className="w-28 h-28 rounded-full border-8 border-slate-100 animate-pulse" />
                            </div>
                            <div className="flex-1 space-y-2.5 w-full">
                              <div className="h-4 bg-slate-100 rounded w-full animate-pulse" />
                              <div className="h-4 bg-slate-100 rounded w-5/6 animate-pulse" />
                            </div>
                          </div>
                        </div>
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
                          <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
                            <div className="h-6 bg-slate-100 rounded animate-pulse w-36" />
                            <div className="h-4 bg-slate-100 rounded animate-pulse w-16" />
                          </div>
                          <div className="flex-1 space-y-3.5 py-2">
                            {[...Array(4)].map((_, i) => (
                              <div key={i} className="flex justify-between items-center">
                                <div className="h-4 bg-slate-100 rounded w-24 animate-pulse" />
                                <div className="h-4 bg-slate-100 rounded w-12 animate-pulse" />
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <InventorySummary data={metrics || undefined} />
                      )}
                    </div>

                    <div className="lg:col-span-2 relative border border-slate-100 rounded-2xl p-6 bg-white overflow-hidden h-[280px]">
                      <div className="absolute inset-0 bg-slate-50/60 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center text-center p-4">
                        <span className="bg-blue-50 text-blue-700 text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full mb-2 shadow-sm border border-blue-100">
                          Coming Soon
                        </span>
                        <p className="text-xs font-bold text-slate-700">Real-Time Driver GPS Tracking</p>
                        <p className="text-[11px] text-slate-400 mt-0.5 max-w-[200px]">Lightweight PWA integration with browser-native HTML5 location tracking is on the immediate horizon.</p>
                      </div>
                      <div className="opacity-25 pointer-events-none h-full">
                        <LiveDeliveries viewAllHref="/dashboard/shipments" />
                      </div>
                    </div>
                  </div>

                  {/* D. Audit Log Row 4 */}
                  <div className="w-full">
                    {isLoading ? (
                      <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between">
                        <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
                          <div className="h-6 bg-slate-100 rounded animate-pulse w-32" />
                        </div>
                        <div className="space-y-4 my-2 flex-1">
                          <div className="h-5 bg-slate-100 rounded w-full animate-pulse" />
                        </div>
                      </div>
                    ) : (
                      <ActivityFeed activities={activities} viewAllHref="/dashboard/reports" />
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </main>
      </div>

      <WhatsAppSimulator
        activeTenantId={tenantId}
        onSuccess={refreshAll}
      />

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
