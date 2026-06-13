"use client";

import React, { useState } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import MetricCards from "@/components/MetricCards";
import RecentOrders from "@/components/RecentOrders";
import CollectionsDonut from "@/components/CollectionsDonut";
import LiveDeliveries from "@/components/LiveDeliveries";
import InventorySummary from "@/components/InventorySummary";
import ActivityFeed from "@/components/ActivityFeed";
import { useDashboardData } from "@/hooks/useDashboardData";
import { ChevronDown, SlidersHorizontal, RefreshCw } from "lucide-react";
import WhatsAppSimulator from "@/components/WhatsAppSimulator";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [activeTenantId, setActiveTenantId] = useState("d3b07384-d113-4956-a5d2-64be7357c11d");

  // Get active tenant name
  const getTenantName = () => {
    switch (activeTenantId) {
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
  } = useDashboardData(activeTenantId);

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
          activeTenantId={activeTenantId}
          setActiveTenantId={setActiveTenantId}
          tenantName={getTenantName()}
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

              {/* Date Filter Dropdown */}
              <button className="flex items-center gap-2 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm">
                <span>21 May – 27 May, 2025</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

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
              />
            </div>

            {/* Right Col: Collections Donut Chart (40% width) */}
            <div className="lg:col-span-2 min-h-[380px]">
              <CollectionsDonut data={donutData} />
            </div>
          </div>

          {/* C. Bottom Operational Grid (Live Map, Stock Summary, Activity Feed) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="min-h-[300px]">
              <LiveDeliveries />
            </div>
            <div className="min-h-[300px]">
              <InventorySummary />
            </div>
            <div className="min-h-[300px]">
              <ActivityFeed activities={activities} />
            </div>
          </div>
        </main>
      </div>

      {/* WhatsApp Ingestion Live testing simulator */}
      <WhatsAppSimulator
        activeTenantId={activeTenantId}
        onSuccess={refreshAll}
      />
    </div>
  );
}
