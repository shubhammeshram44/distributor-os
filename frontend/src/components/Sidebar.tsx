"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShoppingCart,
  Box,
  Layers,
  Users,
  Truck,
  CreditCard,
  BarChart3,
  FileText,
  Zap,
  HelpCircle,
  Settings,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Globe,
  LogOut
} from "lucide-react";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  tenantName: string;
}

export default function Sidebar({ activeTab, setActiveTab, tenantName }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isCollapsed, setIsCollapsed] = useState(false);

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

  // Sync with localStorage and body classes on load
  useEffect(() => {
    const stored = localStorage.getItem("sidebarCollapsed") === "true";
    setIsCollapsed(stored);
    if (stored) {
      document.body.classList.add("sidebar-collapsed");
    } else {
      document.body.classList.remove("sidebar-collapsed");
    }
  }, []);

  const toggleCollapse = () => {
    const nextVal = !isCollapsed;
    setIsCollapsed(nextVal);
    localStorage.setItem("sidebarCollapsed", String(nextVal));
    if (nextVal) {
      document.body.classList.add("sidebar-collapsed");
    } else {
      document.body.classList.remove("sidebar-collapsed");
    }
  };

  const menuItems = [
    { name: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
    { name: "Messages", icon: MessageSquare, href: "/dashboard/messages" },
    { name: "Orders", icon: ShoppingCart, href: "/dashboard/orders" },
    { name: "Inventory", icon: Box, href: "/dashboard/inventory" },
    { name: "Products", icon: Layers, href: "/dashboard/products" },
    { name: "Customers", icon: Users, href: "/dashboard/customers" },
    { name: "Shipments", icon: Truck, href: "/dashboard/shipments" },
    { name: "Collections", icon: CreditCard, href: "/dashboard/collections" },
    { name: "Sales Analytics", icon: BarChart3, href: "/dashboard/sales-analytics" },
    { name: "Reports", icon: FileText, href: "/dashboard/reports" },
    { name: "Team Settings", icon: Settings, href: "/dashboard/settings/team" },
    { name: "Automations", icon: Zap }
  ];

  return (
    <aside className={`${isCollapsed ? 'w-16' : 'w-64'} bg-brand-dark text-white flex flex-col h-screen fixed left-0 top-0 border-r border-brand-darkHover z-20 transition-all duration-300 ease-in-out`}>
      {/* Brand Header */}
      <div className={`h-16 flex items-center ${isCollapsed ? 'justify-center px-2' : 'px-6'} border-b border-brand-darkHover gap-2 transition-all duration-300`}>
        <div className="w-8 h-8 rounded bg-brand-blue flex items-center justify-center font-bold text-lg text-white flex-shrink-0">
          D
        </div>
        {!isCollapsed && (
          <span className="font-semibold text-lg tracking-wider transition-opacity duration-200">
            DistributorOS
          </span>
        )}
      </div>

      {/* Navigation Links */}
      <nav className={`flex-1 ${isCollapsed ? 'px-2' : 'px-4'} py-6 space-y-1.5 overflow-y-auto`}>
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.href
            ? (item.href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(item.href))
            : activeTab === item.name;

          const className = `w-full flex items-center ${
            isCollapsed ? 'justify-center p-3' : 'gap-3 px-4 py-3'
          } rounded-lg text-sm font-medium transition-all text-left relative group ${
            isActive
              ? "bg-brand-blue text-white shadow-md shadow-brand-blue/20"
              : "text-brand-textMuted hover:bg-brand-darkHover hover:text-white"
          }`;

          const tooltip = isCollapsed && (
            <span className="absolute left-full ml-3 px-2 py-1 bg-slate-950 text-white text-xs rounded-md whitespace-nowrap shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 invisible group-hover:visible">
              {item.name}
            </span>
          );

          if (item.href) {
            return (
              <Link
                key={item.name}
                href={item.href}
                className={className}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!isCollapsed && <span className="ml-3 transition-opacity duration-200">{item.name}</span>}
                {tooltip}
              </Link>
            );
          }

          return (
            <button
              key={item.name}
              onClick={() => setActiveTab(item.name)}
              className={className}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!isCollapsed && <span className="ml-3 transition-opacity duration-200">{item.name}</span>}
              {tooltip}
            </button>
          );
        })}
      </nav>

      {/* Profile & Help Area */}
      <div className={`p-4 border-t border-brand-darkHover bg-brand-dark relative flex flex-col ${isCollapsed ? 'items-center gap-4' : 'gap-3'}`}>
        {/* Toggle Collapse Button */}
        <button
          onClick={toggleCollapse}
          className={`absolute -top-10 bg-brand-blue border border-brand-darkHover text-white p-1 rounded-full shadow-lg hover:bg-brand-blue/80 transition-all z-30 cursor-pointer ${
            isCollapsed ? 'left-1/2 -translate-x-1/2' : 'right-4'
          }`}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {/* Help Link */}
        {isCollapsed ? (
          <div className="group relative w-full flex justify-center">
            <button className="p-2 text-brand-textMuted hover:bg-brand-darkHover hover:text-white rounded-lg transition-all">
              <HelpCircle className="w-5 h-5" />
            </button>
            <span className="absolute left-full ml-3 px-2 py-1 bg-slate-950 text-white text-xs rounded-md whitespace-nowrap shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 invisible group-hover:visible">
              Need Help?
            </span>
          </div>
        ) : (
          <button className="w-full flex items-center gap-3 p-3 rounded-lg text-brand-textMuted hover:bg-brand-darkHover hover:text-white text-sm transition-all">
            <HelpCircle className="w-5 h-5 flex-shrink-0" />
            <div className="text-left">
              <p className="font-semibold text-xs text-white">Need help?</p>
              <p className="text-[10px]">Contact Support</p>
            </div>
          </button>
        )}

        {/* View Marketing Site */}
        {isCollapsed ? (
          <div className="group relative w-full flex justify-center">
            <Link href="/" className="p-2 text-brand-textMuted hover:bg-brand-darkHover hover:text-white rounded-lg transition-all">
              <Globe className="w-5 h-5" />
            </Link>
            <span className="absolute left-full ml-3 px-2 py-1 bg-slate-950 text-white text-xs rounded-md whitespace-nowrap shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 invisible group-hover:visible">
              View Marketing Site
            </span>
          </div>
        ) : (
          <Link href="/" className="w-full flex items-center gap-3 p-3 rounded-lg text-brand-textMuted hover:bg-brand-darkHover hover:text-white text-sm transition-all">
            <Globe className="w-5 h-5 flex-shrink-0" />
            <div className="text-left">
              <p className="font-semibold text-xs text-white">View Marketing Site</p>
              <p className="text-[10px]">Back to homepage</p>
            </div>
          </Link>
        )}

        {/* Logout Button */}
        {isCollapsed ? (
          <div className="group relative w-full flex justify-center">
            <button
              onClick={handleLogout}
              className="p-2 text-brand-textMuted hover:bg-brand-darkHover hover:text-white rounded-lg transition-all cursor-pointer"
            >
              <LogOut className="w-5 h-5" />
            </button>
            <span className="absolute left-full ml-3 px-2 py-1 bg-slate-950 text-white text-xs rounded-md whitespace-nowrap shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 invisible group-hover:visible">
              Log Out
            </span>
          </div>
        ) : (
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 p-3 rounded-lg text-brand-textMuted hover:bg-brand-darkHover hover:text-white text-sm transition-all cursor-pointer"
          >
            <LogOut className="w-5 h-5 flex-shrink-0" />
            <div className="text-left">
              <p className="font-semibold text-xs text-white">Log Out</p>
              <p className="text-[10px]">End your session</p>
            </div>
          </button>
        )}

        {/* Tenant Profile */}
        <div className={`flex items-center ${isCollapsed ? 'justify-center p-0 bg-transparent' : 'gap-3 p-2 bg-brand-darkHover rounded-lg'} overflow-hidden transition-all duration-300 w-full`}>
          <div className="w-10 h-10 rounded-full bg-brand-blue flex items-center justify-center font-bold text-white shadow-inner flex-shrink-0">
            {tenantName ? tenantName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : ""}
          </div>
          {!isCollapsed && (
            <div className="text-left overflow-hidden transition-opacity duration-200">
              <h4 className="font-semibold text-sm truncate text-white">{tenantName}</h4>
              <p className="text-xs text-brand-textMuted truncate">Primary Admin</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

