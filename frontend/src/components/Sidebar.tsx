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
  Bell,
  Menu,
  X
} from "lucide-react";
import { FEATURE_FLAGS } from "@/lib/featureFlags";


interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  tenantName: string;
}

export default function Sidebar({ activeTab, setActiveTab, tenantName }: SidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(true);

  // Track viewport so the icon-only "collapsed" style only ever applies at desktop widths —
  // the mobile drawer always shows full labels regardless of the desktop collapse preference.
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const effectiveCollapsed = isCollapsed && isDesktop;

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

  // Close the mobile drawer automatically on route change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

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
      // Messages tab is still WIP — kept behind a feature flag (disabled by default)
      // until the chat experience is ready for real customers.
      ...(FEATURE_FLAGS.messages
        ? [{ name: "Messages", icon: MessageSquare, href: "/dashboard/messages" }]
        : []),
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
      // In-progress rework of the Integrations page — only surfaced outside production
      // builds so real customers never see an internal "(Test)" nav item, while the
      // team can still reach it locally/in staging for QA.
      ...(process.env.NODE_ENV !== "production"
        ? [{ name: "Integrations V2 (Test)", icon: Link2, href: "/dashboard/settings/integrations-v2" }]
        : []),
      { name: "Notifications", icon: Bell, href: "/dashboard/settings/notifications" },
      { name: "Payments", icon: CreditCard, href: "/dashboard/settings/payments" },
      { name: "Automations", icon: Zap, badge: "Soon" }
    ];



  return (
    <>
      {/* Mobile hamburger trigger — only visible below md, replaces the hidden sidebar */}
      <button
        onClick={() => setIsMobileOpen(true)}
        className="md:hidden fixed top-3 left-3 z-30 w-10 h-10 flex items-center justify-center rounded-lg bg-brand-dark text-white shadow-lg"
        aria-label="Open navigation menu"
        aria-expanded={isMobileOpen}
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Backdrop overlay for mobile drawer */}
      {isMobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-20"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`${isCollapsed ? 'md:w-16' : 'md:w-64'} w-64 bg-brand-dark text-white flex flex-col h-screen fixed left-0 top-0 border-r border-brand-darkHover z-30 transition-all duration-300 ease-in-out ${isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
          }`}
      >
        {/* Brand Header */}
        <div className={`h-16 flex items-center ${isCollapsed ? 'md:justify-center md:px-2' : 'px-6'} justify-between border-b border-brand-darkHover gap-2 transition-all duration-300`}>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-brand-blue flex items-center justify-center font-bold text-lg text-white flex-shrink-0">
              D
            </div>
            {!effectiveCollapsed && (
              <span className="font-semibold text-lg tracking-wider transition-opacity duration-200">
                DistributorOS
              </span>
            )}
          </div>
          {/* Close button — mobile drawer only */}
          <button
            onClick={() => setIsMobileOpen(false)}
            className="md:hidden text-brand-textMuted hover:text-white p-1"
            aria-label="Close navigation menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className={`flex-1 ${isCollapsed ? 'md:px-2' : ''} px-4 py-6 space-y-1.5 overflow-y-auto`}>
          {menuItems.map((item) => {
            if (item.type === "category") {
              if (effectiveCollapsed) return <div key={item.name} className="h-px bg-brand-darkHover my-4" />;
              return (
                <div key={item.name} className="px-4 pt-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  {item.name}
                </div>
              );
            }

            const Icon = item.icon;
            // Match on exact path or a full path-segment boundary only — a naive
            // `pathname.startsWith(item.href)` would also match "/dashboard/settings/integrations-v2"
            // against the "Integrations" item's href ("/dashboard/settings/integrations"), since one
            // string is a literal prefix of the other, causing both menu items to render as active
            // at once. Requiring a trailing "/" (or an exact match) enforces a real segment boundary.
            const isActive = item.href
              ? (item.href === "/dashboard"
                ? pathname === "/dashboard" || pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`))
              : activeTab === item.name;

            const className = `w-full flex items-center ${effectiveCollapsed ? 'justify-center p-3' : 'gap-3 px-4 py-3'
              } rounded-lg text-sm font-medium transition-all text-left relative group ${isActive
                ? "bg-brand-blue text-white shadow-md shadow-brand-blue/20"
                : "text-brand-textMuted hover:bg-brand-darkHover hover:text-white"
              }`;

            const tooltip = effectiveCollapsed && (
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
                  {!effectiveCollapsed && (
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
                {!effectiveCollapsed && <span className="ml-3 transition-opacity duration-200">{item.name}</span>}
                {tooltip}
              </button>
            );
          })}
        </nav>

        {/* Desktop-only collapse toggle — mobile drawer uses the close button instead */}
        <button
          onClick={toggleCollapse}
          className="hidden md:flex items-center justify-center gap-2 h-12 border-t border-brand-darkHover text-brand-textMuted hover:bg-brand-darkHover hover:text-white transition-all"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          {!isCollapsed && <span className="text-xs font-semibold">Collapse</span>}
        </button>
      </aside>
    </>
  );
}

