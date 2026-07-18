"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import { Search, MessageSquare, ChevronDown, LogOut, HelpCircle, Globe, X } from "lucide-react";
import { useRouter } from "next/navigation";

interface SearchResult {
  type: "order" | "customer" | "product";
  id: string;
  label: string;
  sublabel?: string;
  href: string;
}

interface DashboardHeaderProps {
  activeTenantId?: string;
  setActiveTenantId?: (id: string) => void;
  tenantName?: string;
  userProfile?: any;
  onTenantChange?: (id: string) => void;
}

export default function DashboardHeader({
  activeTenantId = "",
  setActiveTenantId,
  tenantName = "My Workspace",
  userProfile,
  onTenantChange
}: DashboardHeaderProps) {

  const router = useRouter();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const tenantId = activeTenantId || (typeof window !== "undefined" ? localStorage.getItem("tenant_id") : "");

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim() || !tenantId) { setSearchResults([]); return; }
    setSearchLoading(true);
    try {
      const [ordersRes, customersRes, productsRes] = await Promise.allSettled([
        fetch(`${apiBase}/api/v1/orders?tenant_id=${tenantId}&search=${encodeURIComponent(q)}&limit=4`, { credentials: "include" }),
        fetch(`${apiBase}/api/v1/customers?tenant_id=${tenantId}&search=${encodeURIComponent(q)}&limit=4`, { credentials: "include" }),
        fetch(`${apiBase}/api/v1/products?tenant_id=${tenantId}&search=${encodeURIComponent(q)}&limit=4`, { credentials: "include" }),
      ]);

      const results: SearchResult[] = [];

      if (ordersRes.status === "fulfilled" && ordersRes.value.ok) {
        const d = await ordersRes.value.json();
        (d.items || []).forEach((o: any) => results.push({ type: "order", id: o.id, label: o.order_id, sublabel: `${o.customer} · ₹${o.amount?.toFixed(0)}`, href: `/dashboard/orders` }));
      }
      if (customersRes.status === "fulfilled" && customersRes.value.ok) {
        const d = await customersRes.value.json();
        (d.items || []).forEach((c: any) => results.push({ type: "customer", id: c.id, label: c.retailer_name, sublabel: c.phone, href: `/dashboard/customers` }));
      }
      if (productsRes.status === "fulfilled" && productsRes.value.ok) {
        const d = await productsRes.value.json();
        (d.items || []).forEach((p: any) => results.push({ type: "product", id: p.id, label: p.sku_id, sublabel: `${p.brand} ${p.category}`, href: `/dashboard/products` }));
      }

      setSearchResults(results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [tenantId, apiBase]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);
    setSearchOpen(true);
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    if (!val.trim()) { setSearchResults([]); return; }
    searchDebounceRef.current = setTimeout(() => runSearch(val), 400);
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!(e.target as Element).closest("[data-search-container]")) {
        setSearchOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const typeLabel: Record<string, string> = { order: "Order", customer: "Customer", product: "Product" };
  const typeColor: Record<string, string> = {
    order: "bg-blue-50 text-blue-700",
    customer: "bg-emerald-50 text-emerald-700",
    product: "bg-purple-50 text-purple-700",
  };

  const handleLogout = async () => {
    const token = localStorage.getItem("accessToken");
    try {
      await fetch(`${apiBase}/api/v1/auth/logout`, {
        method: "POST", credentials: "include",
        headers: { "Accept": "application/json", "Content-Type": "application/json", ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
      });
    } catch (err) { console.error("Logout request failed:", err); }
    localStorage.clear();
    window.location.href = "/auth";
  };

  const displayProfile = userProfile || (() => {
    if (typeof window !== "undefined") {
      const storedTenantId = localStorage.getItem("tenant_id");
      if (storedTenantId) {
        return {
          full_name: localStorage.getItem("userFullName") || "",
          role: localStorage.getItem("userRole") || "",
          tenant: { id: storedTenantId, name: localStorage.getItem("tenant_name") || "My Workspace" }
        };
      }
    }
    return null;
  })();

  return (
    <header className="h-16 bg-white border-b border-dashboard-border flex items-center justify-between px-8 fixed top-0 right-0 left-64 z-10 shadow-sm">
      {/* Search Input with Dropdown */}
      <div className="flex items-center gap-4 flex-1 max-w-lg" data-search-container>
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search orders, customers, products..."
            value={searchQuery}
            onChange={handleSearchChange}
            onFocus={() => { if (searchQuery) setSearchOpen(true); }}
            className="w-full pl-10 pr-8 py-2 border border-dashboard-border rounded-lg text-sm bg-slate-50 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:bg-white transition-all text-slate-700"
            aria-label="Global search"
            aria-autocomplete="list"
            aria-expanded={searchOpen && searchResults.length > 0}
          />
          {searchQuery && (
            <button
              onClick={() => { setSearchQuery(""); setSearchResults([]); setSearchOpen(false); searchInputRef.current?.focus(); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Search Results Dropdown */}
          {searchOpen && searchQuery && (
            <div className="absolute top-full mt-1.5 left-0 right-0 bg-white border border-dashboard-border rounded-xl shadow-xl z-50 overflow-hidden">
              {searchLoading ? (
                <div className="px-4 py-3 text-xs text-slate-500 font-medium animate-pulse">Searching...</div>
              ) : searchResults.length === 0 ? (
                <div className="px-4 py-3 text-xs text-slate-400 font-medium">No results for &ldquo;{searchQuery}&rdquo;</div>
              ) : (
                <ul role="listbox">
                  {searchResults.map((r) => (
                    <li key={`${r.type}-${r.id}`} role="option">
                      <Link
                        href={r.href}
                        onClick={() => { setSearchQuery(""); setSearchOpen(false); }}
                        className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-all"
                      >
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${typeColor[r.type]}`}>
                          {typeLabel[r.type]}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-slate-800 truncate">{r.label}</p>
                          {r.sublabel && <p className="text-[10px] text-slate-400 truncate">{r.sublabel}</p>}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Actions & User Area */}
      <div className="flex items-center gap-6">
        {/* Workspace Label — static (single-tenant per user today). Not a dropdown: don't imply switching that doesn't exist. */}
        <div className="flex items-center gap-2 border-r border-dashboard-border pr-6">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Workspace</span>
          <span
            className="px-3 py-1.5 border border-dashboard-border rounded-lg text-xs font-semibold text-slate-700 bg-slate-50 truncate max-w-[160px]"
            title={displayProfile?.tenant?.name || "My Workspace"}
          >
            {displayProfile?.tenant?.name || "Loading..."}
          </span>
        </div>

        {/* Notifications */}
        <div className="flex items-center gap-4">
          <Link href="/dashboard/messages" className="relative p-2 text-slate-500 hover:bg-slate-50 rounded-full transition-all" aria-label="Messages">
            <MessageSquare className="w-5 h-5 text-emerald-600" />
          </Link>
        </div>

        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center gap-3 pl-2 border-l border-dashboard-border hover:opacity-80 transition-all focus:outline-none bg-transparent border-none"
            aria-label="User profile menu"
            aria-expanded={isProfileOpen}
            aria-haspopup="true"
          >
            <div className="text-right hidden sm:block">
              <h5 className="font-semibold text-sm text-slate-800">{displayProfile?.full_name ? `Hi, ${displayProfile.full_name}` : ""}</h5>
              <p className="text-[10px] text-slate-400 font-medium">{displayProfile?.role || ""}</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-slate-200 border border-slate-300 shadow-sm flex items-center justify-center text-xs font-bold text-slate-700 flex-shrink-0">
              {displayProfile?.full_name ? displayProfile.full_name.charAt(0).toUpperCase() : "U"}
            </div>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-52 bg-white border border-dashboard-border rounded-xl shadow-xl py-2 z-50">
              <div className="px-4 py-2 border-b border-dashboard-border mb-1">
                <p className="text-xs font-bold text-slate-800 truncate">{displayProfile?.full_name}</p>
                <p className="text-[10px] font-semibold text-slate-400 truncate">{displayProfile?.role}</p>
              </div>
              <Link href="mailto:support@distributoros.com" className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all" onClick={() => setIsProfileOpen(false)}>
                <HelpCircle className="w-4 h-4 text-slate-400" />
                <span>Need help?</span>
              </Link>
              <Link href="/" className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all block" onClick={() => setIsProfileOpen(false)}>
                <Globe className="w-4 h-4 text-slate-400" />
                <span>View marketing site</span>
              </Link>
              <hr className="border-dashboard-border my-1" />
              <button onClick={handleLogout} className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-bold text-rose-600 hover:bg-rose-50 transition-all text-left bg-transparent border-none">
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

