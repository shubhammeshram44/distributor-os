"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Settings,
  Link2,
  Bell
} from "lucide-react";


interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  tenantName: string;
}

export default function Sidebar({ activeTab, setActiveTab, tenantName }: SidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);

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

  const menuItems: {
    name: string;
    icon?: any;
    href?: string;
    type?: string;
    badge?: string;
  }[] = [
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
    { type: "category", name: "Settings" },
    { name: "Team Settings", icon: Settings, href: "/dashboard/settings/team" },
    { name: "Integrations", icon: Link2, href: "/dashboard/settings/integrations" },
    { name: "Integrations V2 (Test)", icon: Link2, href: "/dashboard/settings/integrations-v2" },
    { name: "Notifications", icon: Bell, href: "/dashboard/settings/notifications" },
    { name: "Payments", icon: CreditCard, href: "/dashboard/settings/payments" },
    { name: "Automations", icon: Zap, badge: "Soon" }
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

      <nav className={`flex-1 ${isCollapsed ? 'px-2' : 'px-4'} py-6 space-y-1.5 overflow-y-auto`}>
        {menuItems.map((item) => {
          if (item.type === "category") {
            if (isCollapsed) return <div key={item.name} className="h-px bg-brand-darkHover my-4" />;
            return (
              <div key={item.name} className="px-4 pt-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                {item.name}
              </div>
            );
          }

          const Icon = item.icon;
          const isActive = item.href

            ? (item.href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(item.href))
            : activeTab === item.name;

          const className = `w-full flex items-center ${isCollapsed ? 'justify-center p-3' : 'gap-3 px-4 py-3'
            } rounded-lg text-sm font-medium transition-all text-left relative group ${isActive
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
                aria-label={item.name}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!isCollapsed && (
                  <span className="ml-3 transition-opacity duration-200 flex items-center gap-2">
                    {item.name}
                    {item.badge && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 bg-slate-600 text-slate-200 rounded-full uppercase tracking-wide">
                        {item.badge}
                      </span>
                    )}
                  </span>
                )}
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
    </aside>
  );
}

