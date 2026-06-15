"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Search, MessageSquare, ChevronDown, LogOut, HelpCircle, Globe } from "lucide-react";

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
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const handleLogout = async () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const token = localStorage.getItem("accessToken");

    try {
      // Notify backend server to discard cross-site session cookies
      await fetch(`${apiBase}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        }
      });
    } catch (err) {
      console.error("Server-side session teardown log incomplete:", err);
    }

    // Explicitly purge all local caching keys from client storage
    localStorage.clear();
    
    // Clear cookie fallback via explicit window location assignment
    window.location.href = "/auth";
  };
  // Use the parent-provided userProfile directly; no redundant /auth/me fetch
  // The parent dashboard page already handles authentication and 401 redirects
  const displayProfile = userProfile || (() => {
    // Fallback: construct a minimal profile from localStorage for sub-pages
    if (typeof window !== "undefined") {
      const storedName = localStorage.getItem("tenant_name");
      const storedFullName = localStorage.getItem("userFullName");
      const storedRole = localStorage.getItem("userRole");
      const storedTenantId = localStorage.getItem("tenant_id");
      if (storedTenantId) {
        return {
          full_name: storedFullName || "",
          role: storedRole || "",
          tenant: { id: storedTenantId, name: storedName || "My Workspace" }
        };
      }
    }
    return null;
  })();

  return (
    <header className="h-16 bg-white border-b border-dashboard-border flex items-center justify-between px-8 fixed top-0 right-0 left-64 z-10 shadow-sm">
      {/* Search Input */}
      <div className="flex items-center gap-4 flex-1 max-w-lg">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search orders, customers, products..."
            className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-slate-50 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:bg-white transition-all text-slate-700"
          />
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
              {displayProfile?.tenant ? (
                <option value={displayProfile.tenant.id}>
                  {displayProfile.tenant.name || "My Workspace"}
                </option>
              ) : (
                <option value="">Loading Workspace Account...</option>
              )}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Notifications & Badges */}
        <div className="flex items-center gap-4">


          {/* WhatsApp Webhook alert count */}
          <Link href="/dashboard/messages" className="relative p-2 text-slate-500 hover:bg-slate-50 rounded-full transition-all cursor-pointer">
            <MessageSquare className="w-5 h-5 text-emerald-600" />
            <span className="absolute top-0 right-0 w-4.5 h-4.5 bg-emerald-500 text-[9px] font-bold text-white rounded-full flex items-center justify-center border-2 border-white">
              8
            </span>
          </Link>


        </div>

        {/* User Profile with Dropdown */}
        <div className="relative">
          <button 
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center gap-3 pl-2 border-l border-dashboard-border hover:opacity-80 transition-all cursor-pointer focus:outline-none bg-transparent border-none"
            aria-label="User Profile Menu"
          >
            <div className="text-right">
              <h5 className="font-semibold text-sm text-slate-800">
                {displayProfile?.full_name ? `Hi, ${displayProfile.full_name}` : ""}
              </h5>
              <p className="text-[10px] text-slate-400 font-medium">
                {displayProfile?.role || ""}
              </p>
            </div>
            <div className="w-9 h-9 rounded-full bg-slate-200 overflow-hidden border border-slate-300 shadow-sm flex items-center justify-center text-xs font-bold text-slate-700">
              {displayProfile?.full_name ? displayProfile.full_name.charAt(0).toUpperCase() : ""}
            </div>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-52 bg-white border border-dashboard-border rounded-xl shadow-xl py-2 z-50 animate-fade-in">
              <div className="px-4 py-2 border-b border-dashboard-border mb-1 text-left">
                <p className="text-xs font-bold text-slate-800 truncate">{displayProfile?.full_name}</p>
                <p className="text-[10px] font-semibold text-slate-400 truncate">{displayProfile?.role}</p>
              </div>

              {/* Need help */}
              <button 
                onClick={() => {
                  alert("Support Contact: support@distributoros.com");
                  setIsProfileOpen(false);
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all text-left cursor-pointer border-none bg-transparent"
              >
                <HelpCircle className="w-4 h-4 text-slate-400" />
                <span>Need help?</span>
              </button>

              {/* View marketing site */}
              <Link 
                href="/"
                onClick={() => setIsProfileOpen(false)}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-all text-left block"
              >
                <Globe className="w-4 h-4 text-slate-400" />
                <span>View marketing site</span>
              </Link>

              <hr className="border-dashboard-border my-1" />

              {/* Log out */}
              <button 
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-bold text-rose-600 hover:bg-rose-50 hover:text-rose-700 transition-all text-left cursor-pointer border-none bg-transparent"
              >
                <LogOut className="w-4 h-4 text-rose-500" />
                <span>Log out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
