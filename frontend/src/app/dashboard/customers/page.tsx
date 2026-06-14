"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  Users,
  CheckCircle2,
  X,
  TrendingUp,
  AlertTriangle,
  Coins
} from "lucide-react";

interface CustomerRow {
  id: string;
  customer_id: string;
  retailer_name: string;
  address_text: string;
  gstin: string;
  tax_group: string;
  phone: string;
  payment_terms: string;
  credit_limit: number;
  outstanding_balance: number;
}

export default function CustomersPage() {
  const [activeTenantId, setActiveTenantId] = useState("d3b07384-d113-4956-a5d2-64be7357c11d");
  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Sync tenant from localStorage on load
  useEffect(() => {
    const stored = localStorage.getItem("activeTenantId");
    if (stored) {
      setActiveTenantId(stored);
    }
  }, []);

  const handleTenantChange = (id: string) => {
    setActiveTenantId(id);
    localStorage.setItem("activeTenantId", id);
  };

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

  // Fetch all customers for active tenant
  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/dashboard/customers?tenant_id=${activeTenantId}`);
      if (!resp.ok) throw new Error("Failed to fetch customers");
      const data = await resp.json();
      setCustomers(data);
      setError(null);
    } catch (err: any) {
      console.error("Customers load failed:", err);
      setError(err.message || "Failed to load customers from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  // Filter Logic
  const filteredCustomers = customers.filter(c => {
    const query = searchQuery.toLowerCase();
    return (
      c.customer_id.toLowerCase().includes(query) ||
      c.retailer_name.toLowerCase().includes(query) ||
      c.phone.toLowerCase().includes(query) ||
      c.address_text.toLowerCase().includes(query)
    );
  });

  // Derived Metrics
  const totalCustomersCount = customers.length;
  const totalOutstanding = customers.reduce((sum, c) => sum + c.outstanding_balance, 0);
  const atRiskCount = customers.filter(c => {
    if (c.credit_limit <= 0) return false;
    return c.outstanding_balance / c.credit_limit >= 0.9;
  }).length;

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      <Sidebar
        activeTab="Customers"
        setActiveTab={() => {}}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {/* Header Controls */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-blue" />
                <span>Customers Hub</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Manage retailer accounts, billing parameters, outstanding collections, and credit guardrail limits
              </p>
            </div>

            <button
              onClick={fetchCustomers}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Ledger</span>
            </button>
          </div>

          {/* Quick Metrics Banners */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Total Customers */}
            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Retailers</p>
                <h3 className="text-2xl font-extrabold text-slate-800 mt-1">{totalCustomersCount}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Active billing relationships</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-brand-blue shadow-sm">
                <Users className="w-5 h-5" />
              </div>
            </div>

            {/* Total Outstanding */}
            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Outstanding</p>
                <h3 className="text-2xl font-extrabold text-slate-800 mt-1">{formatCurrency(totalOutstanding)}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Uncollected receivables balance</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 shadow-sm">
                <Coins className="w-5 h-5" />
              </div>
            </div>

            {/* Credit At Risk */}
            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Ceiling Risk Accounts</p>
                <h3 className={`text-2xl font-extrabold mt-1 ${atRiskCount > 0 ? "text-rose-600" : "text-slate-800"}`}>
                  {atRiskCount}
                </h3>
                <p className="text-[10px] text-rose-500 font-semibold mt-1">Balances at &gt;= 90% of credit ceiling</p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-sm ${atRiskCount > 0 ? "bg-rose-50 text-rose-600" : "bg-slate-50 text-slate-400"}`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>
          </div>

          {/* Financial Ledger Grid Table Card */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
            {/* Search filter utility bar */}
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 rounded-t-xl gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by Store Name, Customer ID, Address..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700"
                />
              </div>

              <div className="text-xs font-bold text-slate-400">
                Total Retailers Listed: <span className="text-slate-700">{filteredCustomers.length}</span>
              </div>
            </div>

            {/* Customers Grid */}
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading customers ledger...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button
                    onClick={fetchCustomers}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredCustomers.length === 0 ? (
                <div className="text-center text-slate-400 py-24">
                  <p className="text-sm font-medium">No customers found.</p>
                  <p className="text-xs text-slate-400 mt-1">Try refining your filter parameters or verify tenant registration profiles.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                      <th className="py-3 px-6">Customer ID</th>
                      <th className="py-3 px-6">Store Name</th>
                      <th className="py-3 px-6">Contact Number</th>
                      <th className="py-3 px-6">Billing Terms</th>
                      <th className="py-3 px-6 text-right">Credit Ceiling Limit</th>
                      <th className="py-3 px-6 text-right">Current Outstanding</th>
                      <th className="py-3 px-6 text-center">Status Alerts</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredCustomers.map((c) => {
                      const isRisk = c.credit_limit > 0 && (c.outstanding_balance / c.credit_limit) >= 0.9;
                      return (
                        <tr key={c.id} className="hover:bg-slate-50/50 transition-colors group">
                          <td className="py-4 px-6 font-bold text-slate-800 text-sm">
                            {c.customer_id}
                          </td>
                          <td className="py-4 px-6 font-semibold text-slate-700">
                            <div>
                              <p className="font-bold text-slate-800 text-sm">{c.retailer_name}</p>
                              <p className="text-[10px] text-slate-400 font-semibold mt-0.5">{c.address_text}</p>
                            </div>
                          </td>
                          <td className="py-4 px-6 font-medium text-slate-500">
                            {c.phone}
                          </td>
                          <td className="py-4 px-6 text-xs font-semibold text-slate-500">
                            <span className="bg-slate-100 px-2 py-1 rounded border border-slate-200/50">
                              {(c as any).payment_terms || "Net 30"}
                            </span>
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                            {formatCurrency(c.credit_limit)}
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                            {formatCurrency(c.outstanding_balance)}
                          </td>
                          <td className="py-4 px-6 text-center">
                            {isRisk ? (
                              <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-2 py-1 rounded-full text-[10px] font-bold animate-pulse">
                                <AlertTriangle className="w-3 h-3" />
                                <span>Credit At Risk</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-1 rounded-full text-[10px] font-bold">
                                <CheckCircle2 className="w-3 h-3" />
                                <span>Healthy</span>
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </main>
      </div>

      {/* Sleek Floating Toast Notification */}
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
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 transition-all shrink-0 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
