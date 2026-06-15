"use client";

import React from "react";
import Link from "next/link";
import { Search, Bell, MessageSquare, Calendar, ChevronDown } from "lucide-react";

interface DashboardHeaderProps {
  activeTenantId: string;
  setActiveTenantId: (id: string) => void;
  tenantName: string;
  userProfile?: any;
}

export default function DashboardHeader({
  activeTenantId,
  setActiveTenantId,
  tenantName,
  userProfile
}: DashboardHeaderProps) {
  // Available tenants for testing multi-tenant isolation
  const baseTenants = [
    { id: "d3b07384-d113-4956-a5d2-64be7357c11d", name: "S.V. Distributors" },
    { id: "e1c08495-d224-4a67-b6e3-75cf8468d22e", name: "Reliance Distribution" },
    { id: "f2d095a6-e335-5b78-c7f4-86df9579e33f", name: "Vikas Sales Corp" }
  ];

  // Append user's custom tenant dynamically if not present in the default list
  const tenants = [...baseTenants];
  if (userProfile?.tenant?.id) {
    const exists = tenants.some(t => t.id === userProfile.tenant.id);
    if (!exists) {
      tenants.push({
        id: userProfile.tenant.id,
        name: userProfile.tenant.name || "My Workspace"
      });
    }
  }

  return (
    <header className="h-16 bg-white border-b border-dashboard-border flex items-center justify-between px-8 fixed top-0 right-0 left-64 z-10 shadow-sm">
      {/* Search Input and Channel Selector */}
      <div className="flex items-center gap-4 flex-1 max-w-lg">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search orders, customers, products..."
            className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-slate-50 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:bg-white transition-all text-slate-700"
          />
        </div>
        
        {/* Channel Dropdown */}
        <div className="relative">
          <button className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border rounded-lg text-sm text-slate-600 hover:bg-slate-50 font-medium">
            <span>All Channels</span>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>
        </div>
      </div>

      {/* Right Actions & User Area */}
      <div className="flex items-center gap-6">
        {/* Tenant Switcher dropdown */}
        <div className="flex items-center gap-2 border-r border-dashboard-border pr-6">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Tenant:</span>
          <div className="relative">
            <select
              value={activeTenantId}
              onChange={(e) => setActiveTenantId(e.target.value)}
              className="pl-3 pr-8 py-1.5 border border-dashboard-border rounded-lg text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer bg-white appearance-none"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Notifications & Badges */}
        <div className="flex items-center gap-4">
          {/* System Alerts */}
          <button className="relative p-2 text-slate-500 hover:bg-slate-50 rounded-full transition-all">
            <Bell className="w-5 h-5" />
            <span className="absolute top-0 right-0 w-4.5 h-4.5 bg-brand-blue text-[9px] font-bold text-white rounded-full flex items-center justify-center border-2 border-white">
              12
            </span>
          </button>

          {/* WhatsApp Webhook alert count */}
          <Link href="/dashboard/messages" className="relative p-2 text-slate-500 hover:bg-slate-50 rounded-full transition-all cursor-pointer">
            <MessageSquare className="w-5 h-5 text-emerald-600" />
            <span className="absolute top-0 right-0 w-4.5 h-4.5 bg-emerald-500 text-[9px] font-bold text-white rounded-full flex items-center justify-center border-2 border-white">
              8
            </span>
          </Link>

          {/* Calendar Picker */}
          <button className="p-2 text-slate-500 hover:bg-slate-50 rounded-full transition-all">
            <Calendar className="w-5 h-5" />
          </button>
        </div>

        {/* User Profile */}
        <div className="flex items-center gap-3 pl-2 border-l border-dashboard-border">
          <div className="text-right">
            <h5 className="font-semibold text-sm text-slate-800">Hi, {userProfile?.full_name || "Vikram"}</h5>
            <p className="text-[10px] text-slate-400 font-medium">{userProfile?.role || "Super Admin"}</p>
          </div>
          <div className="w-9 h-9 rounded-full bg-slate-200 overflow-hidden border border-slate-300 shadow-sm flex items-center justify-center text-xs font-bold text-slate-700">
            {userProfile?.full_name ? userProfile.full_name.charAt(0).toUpperCase() : "V"}
          </div>
        </div>
      </div>
    </header>
  );
}
