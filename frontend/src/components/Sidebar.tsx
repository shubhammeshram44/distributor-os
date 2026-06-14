"use client";

import React from "react";
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
  HelpCircle
} from "lucide-react";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  tenantName: string;
}

export default function Sidebar({ activeTab, setActiveTab, tenantName }: SidebarProps) {
  const pathname = usePathname();

  const menuItems = [
    { name: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
    { name: "Orders", icon: ShoppingCart, href: "/dashboard/orders" },
    { name: "Inventory", icon: Box, href: "/dashboard/inventory" },
    { name: "Products", icon: Layers, href: "/dashboard/products" },
    { name: "Customers", icon: Users },
    { name: "Shipments", icon: Truck },
    { name: "Collections", icon: CreditCard },
    { name: "Sales Analytics", icon: BarChart3 },
    { name: "Reports", icon: FileText },
    { name: "Automations", icon: Zap }
  ];

  return (
    <aside className="w-64 bg-brand-dark text-white flex flex-col h-screen fixed left-0 top-0 border-r border-brand-darkHover z-20">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-brand-darkHover gap-2">
        <div className="w-8 h-8 rounded bg-brand-blue flex items-center justify-center font-bold text-lg text-white">
          D
        </div>
        <span className="font-semibold text-lg tracking-wider">DistributorOS</span>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.href
            ? (item.href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(item.href))
            : activeTab === item.name;

          const className = `w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all text-left ${
            isActive
              ? "bg-brand-blue text-white shadow-md shadow-brand-blue/20"
              : "text-brand-textMuted hover:bg-brand-darkHover hover:text-white"
          }`;

          if (item.href) {
            return (
              <Link
                key={item.name}
                href={item.href}
                className={className}
              >
                <Icon className="w-5 h-5" />
                <span>{item.name}</span>
              </Link>
            );
          }

          return (
            <button
              key={item.name}
              onClick={() => setActiveTab(item.name)}
              className={className}
            >
              <Icon className="w-5 h-5" />
              <span>{item.name}</span>
            </button>
          );
        })}
      </nav>


      {/* Profile & Help Area */}
      <div className="p-4 border-t border-brand-darkHover bg-brand-dark">
        <button className="w-full flex items-center gap-3 p-3 rounded-lg text-brand-textMuted hover:bg-brand-darkHover hover:text-white text-sm transition-all mb-4">
          <HelpCircle className="w-5 h-5" />
          <div className="text-left">
            <p className="font-semibold text-xs text-white">Need help?</p>
            <p className="text-[10px]">Contact Support</p>
          </div>
        </button>

        <div className="flex items-center gap-3 p-2 rounded-lg bg-brand-darkHover">
          <div className="w-10 h-10 rounded-full bg-brand-blue flex items-center justify-center font-bold text-white shadow-inner">
            SV
          </div>
          <div className="text-left overflow-hidden">
            <h4 className="font-semibold text-sm truncate text-white">{tenantName}</h4>
            <p className="text-xs text-brand-textMuted truncate">Primary Admin</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
