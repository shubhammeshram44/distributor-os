"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { useSearchParams } from "next/navigation";
import Pagination from "@/components/ui/Pagination";
import { formatDateTime } from "@/utils/datetime";
import { useDebounce, fetchWithTimeout } from "@/lib/debounce";
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
  Coins,
  Edit3,
  CreditCard
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

function CustomersContent() {
  const searchParams = useSearchParams();
  const filterParam = searchParams.get("filter");
  const [activeTenantId, setActiveTenantId] = useState("");
  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [totalRetailers, setTotalRetailers] = useState(0);
  const [totalOutstanding, setTotalOutstanding] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Modal States
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerRow | null>(null);
  const [updatedLimit, setUpdatedLimit] = useState("");
  const [updatedTerms, setUpdatedTerms] = useState("");
  const [savingConfig, setSavingConfig] = useState(false);
  const [whatsappNotificationsEnabled, setWhatsappNotificationsEnabled] = useState(true);

  // Onboard Retailer Modal States
  const [isOnboardModalOpen, setIsOnboardModalOpen] = useState(false);
  const [storeName, setStoreName] = useState("");
  const [contactNumber, setContactNumber] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [creditLimit, setCreditLimit] = useState("100000");
  const [billingTerms, setBillingTerms] = useState("Net 30");
  const [savingOnboard, setSavingOnboard] = useState(false);

  // Statement Drawer States
  const [isStatementOpen, setIsStatementOpen] = useState(false);
  const [activeStatementRows, setActiveStatementRows] = useState<any[]>([]);
  const [loadingStatement, setLoadingStatement] = useState(false);
  const [statementCustomerName, setStatementCustomerName] = useState("");

  // Payment history drawer states
  const [isPaymentDrawerOpen, setIsPaymentDrawerOpen] = useState(false);
  const [paymentHistory, setPaymentHistory] = useState<any[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(false);
  const [paymentDrawerCustomer, setPaymentDrawerCustomer] = useState("");

  // Pagination states
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 50;


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
    const stored = localStorage.getItem("tenant_id");
    if (stored) {
      setActiveTenantId(stored);
    }
  }, []);

  const handleTenantChange = (id: string) => {
    setActiveTenantId(id);
    localStorage.setItem("tenant_id", id);
  };

  const getTenantName = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("tenant_name") || "My Workspace";
    }
    return "My Workspace";
  };

  // Fetch all customers for active tenant
  const fetchCustomers = useCallback(async (tenantId?: string, newSkip?: number) => {
    const targetTenant = (typeof tenantId === "string") ? tenantId : activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    const currentSkip = newSkip !== undefined ? newSkip : skip;
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/customers?tenant_id=${targetTenant}&skip=${currentSkip}&limit=${limit}`,
        { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {}, timeout: 12000 }
      );
      if (!resp.ok) throw new Error("Failed to fetch customers");
      const data = await resp.json();
      const items = data.items ?? data;
      setCustomers(items);
      setTotal(data.total ?? items.length);
      setTotalRetailers(data.total ?? items.length);
      setTotalOutstanding(items.reduce((sum: number, c: any) => sum + (c.outstanding_balance ?? 0), 0));
      setError(null);
    } catch (err: any) {
      console.error("Customers load failed:", err);
      setError(err.message || "Failed to load customers from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, skip, limit]);

  useEffect(() => {
    // 1. Immediately wipe out old data rows so they can never leak or persist
    setCustomers([]);

    // 2. Clear out any summary metric banners (Total Retailers, Outstanding Balances)
    setTotalRetailers(0);
    setTotalOutstanding(0);

    // 3. Initiate the secure network request for the new active tenant context
    if (activeTenantId) {
      setSkip(0);
      fetchCustomers(activeTenantId, 0);
    }
  }, [activeTenantId]);

  const handlePageChange = (newSkip: number) => {
    setSkip(newSkip);
    fetchCustomers(activeTenantId, newSkip);
  };

  const handleOpenPaymentHistory = async (customer: CustomerRow) => {
    setPaymentDrawerCustomer(customer.retailer_name);
    setIsPaymentDrawerOpen(true);
    setLoadingPayments(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(
        `${apiBase}/api/v1/customers/${customer.id}/payments?tenant_id=${activeTenantId}`,
        { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (resp.ok) {
        const data = await resp.json();
        setPaymentHistory(data.items ?? []);
      } else {
        showToast("Failed to retrieve payment history.", "error");
        setIsPaymentDrawerOpen(false);
      }
    } catch {
      showToast("Network error loading payment history.", "error");
      setIsPaymentDrawerOpen(false);
    } finally {
      setLoadingPayments(false);
    }
  };

  const handleOpenStatement = async (customer: CustomerRow) => {
    setStatementCustomerName(customer.retailer_name);
    setIsStatementOpen(true);
    setLoadingStatement(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/customers/${customer.id}/statement?tenant_id=${activeTenantId}`, {
        credentials: "include"
      });
      if (resp.ok) {
        const data = await resp.json();
        setActiveStatementRows(data.statement);
      } else {
        showToast("Failed to retrieve statement history.", "error");
      }
    } catch (err) {
      console.error("Statement retrieve failed:", err);
      showToast("Network connection breakdown during statement fetch.", "error");
    } finally {
      setLoadingStatement(false);
    }
  };


  const toggleCustomerWhatsappPrefs = async () => {
    if (!selectedCustomer) return;
    const targetId = selectedCustomer.id;
    const nextVal = !whatsappNotificationsEnabled;

    // Optimistic UI updates
    setWhatsappNotificationsEnabled(nextVal);
    setCustomers(prev => prev.map(c => c.id === targetId ? { ...c, whatsapp_notifications_enabled: nextVal } as any : c));

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/customers/${targetId}/notification-prefs`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          whatsapp_notifications_enabled: nextVal
        })
      });
      if (resp.ok) {
        showToast("Customer notification preference updated!", "success");
      } else {
        // Rollback
        setWhatsappNotificationsEnabled(!nextVal);
        setCustomers(prev => prev.map(c => c.id === targetId ? { ...c, whatsapp_notifications_enabled: !nextVal } as any : c));
        showToast("Failed to update notification preferences.", "error");
      }
    } catch (err) {
      console.error(err);
      // Rollback
      setWhatsappNotificationsEnabled(!nextVal);
      setCustomers(prev => prev.map(c => c.id === targetId ? { ...c, whatsapp_notifications_enabled: !nextVal } as any : c));
      showToast("Error connecting to server.", "error");
    }
  };

  // Open Edit Modal
  const handleOpenEditModal = (customer: CustomerRow) => {
    setSelectedCustomer(customer);
    setUpdatedLimit(String(customer.credit_limit));
    setUpdatedTerms(customer.payment_terms || "Net 30");
    setWhatsappNotificationsEnabled((customer as any).whatsapp_notifications_enabled !== false);
    setIsEditModalOpen(true);
  };

  // Submit Edit Settings
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomer) return;

    const limitVal = parseFloat(updatedLimit);
    if (isNaN(limitVal) || limitVal < 0) {
      showToast("Credit Limit must be a non-negative number.", "error");
      return;
    }

    setSavingConfig(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/customers/${selectedCustomer.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          credit_limit: limitVal,
          billing_terms: updatedTerms
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast("Customer configuration updated successfully!", "success");
        setIsEditModalOpen(false);
        fetchCustomers(); // Refresh grid instantly
      } else {
        const detail = data.detail || "Failed to update configuration.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during settings update.", "error");
    } finally {
      setSavingConfig(false);
    }
  };

  // Submit Customer Onboarding
  const handleOnboardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!storeName.trim() || !contactNumber.trim() || !deliveryAddress.trim() || !creditLimit.trim()) {
      showToast("All fields are required.", "error");
      return;
    }

    const limitVal = parseFloat(creditLimit);
    if (isNaN(limitVal) || limitVal < 0) {
      showToast("Credit Limit must be a non-negative number.", "error");
      return;
    }

    setSavingOnboard(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          store_name: storeName.trim(),
          contact_number: contactNumber.trim(),
          delivery_address: deliveryAddress.trim(),
          credit_limit: limitVal,
          billing_terms: billingTerms
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast("New retailer onboarded successfully!", "success");
        setIsOnboardModalOpen(false);
        // Reset form
        setStoreName("");
        setContactNumber("");
        setDeliveryAddress("");
        setCreditLimit("100000");
        setBillingTerms("Net 30");
        fetchCustomers(); // Refresh grid instantly
      } else {
        const detail = data.detail || "Failed to onboard customer.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during customer onboarding.", "error");
    } finally {
      setSavingOnboard(false);
    }
  };

  // Filter Logic
  const filteredCustomers = customers.filter(c => {
    if (filterParam === "overdue_60") {
      const isOverdue60 = c.customer_id === "CUST-104" || c.payment_terms === "60+ Days";
      if (!isOverdue60) return false;
    }

    const query = debouncedSearchQuery.toLowerCase();
    return (
      c.customer_id.toLowerCase().includes(query) ||
      c.retailer_name.toLowerCase().includes(query) ||
      c.phone.toLowerCase().includes(query) ||
      c.address_text.toLowerCase().includes(query)
    );
  });

  // Derived Metrics
  const totalCustomersCount = totalRetailers;
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
  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-dashboard-inset">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800 dark:text-slate-100">
      <Sidebar
        activeTab="Customers"
        setActiveTab={() => { }}
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
              <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-blue" />
                <span>Customers Hub</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Manage retailer accounts, billing parameters, outstanding collections, and credit guardrail limits
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsOnboardModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm cursor-pointer animate-fade-in"
              >
                <span>+ Onboard New Retailer</span>
              </button>

              <button
                onClick={() => {
                  if (activeTenantId) {
                    fetchCustomers(activeTenantId);
                  }
                }}
                className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white dark:bg-dashboard-card rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 transition-all shadow-sm cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                <span>Refresh Ledger</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics Banners */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Total Customers */}
            <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Retailers</p>
                <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">{totalCustomersCount}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Active billing relationships</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center text-brand-blue shadow-sm">
                <Users className="w-5 h-5" />
              </div>
            </div>

            {/* Total Outstanding */}
            <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Outstanding</p>
                <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">{formatCurrency(totalOutstanding)}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Uncollected receivables balance</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shadow-sm">
                <Coins className="w-5 h-5" />
              </div>
            </div>

            {/* Credit At Risk */}
            <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Ceiling Risk Accounts</p>
                <h3 className={`text-2xl font-extrabold mt-1 ${atRiskCount > 0 ? "text-rose-600 dark:text-rose-400" : "text-slate-800 dark:text-slate-100"}`}>
                  {atRiskCount}
                </h3>
                <p className="text-[10px] text-rose-500 font-semibold mt-1">Balances at &gt;= 90% of credit ceiling</p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-sm ${atRiskCount > 0 ? "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400" : "bg-slate-50 dark:bg-dashboard-inset text-slate-400"}`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>
          </div>

          {/* Financial Ledger Grid Table Card */}
          <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
            {/* Search filter utility bar */}
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 dark:bg-transparent rounded-t-xl gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by Store Name, Customer ID, Address..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white dark:bg-dashboard-card focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700 dark:text-slate-300"
                />
              </div>

              <div className="text-xs font-bold text-slate-400">
                Total Retailers Listed: <span className="text-slate-700 dark:text-slate-300">{filteredCustomers.length}</span>
              </div>
            </div>

            {/* Customers Grid */}
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Loading customers ledger...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600 dark:text-rose-400">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button
                    onClick={() => {
                      if (activeTenantId) {
                        fetchCustomers(activeTenantId);
                      }
                    }}
                    className="mt-2 px-4 py-2 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-400 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
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
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50 dark:bg-transparent">
                      <th className="py-3 px-6">Customer ID</th>
                      <th className="py-3 px-6">Store Name</th>
                      <th className="py-3 px-6">Contact Number</th>
                      <th className="py-3 px-6">Billing Terms</th>
                      <th className="py-3 px-6 text-right">Credit Ceiling Limit</th>
                      <th className="py-3 px-6 text-right">Current Outstanding</th>
                      <th className="py-3 px-6 text-center">Status Alerts</th>
                      <th className="py-3 px-6 text-center">Statement</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {filteredCustomers.map((c) => {
                      const isRisk = c.credit_limit > 0 && (c.outstanding_balance / c.credit_limit) >= 0.9;
                      return (
                        <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-white/5 transition-colors group">
                          <td className="py-4 px-6 font-bold text-slate-800 dark:text-slate-100 text-sm">
                            {c.customer_id}
                          </td>
                          <td className="py-4 px-6 font-semibold text-slate-700 dark:text-slate-300">
                            <div>
                              <p className="font-bold text-slate-800 dark:text-slate-100 text-sm">{c.retailer_name}</p>
                              <p className="text-[10px] text-slate-400 font-semibold mt-0.5">{c.address_text}</p>
                            </div>
                          </td>
                          <td className="py-4 px-6 font-medium text-slate-500 dark:text-slate-400">
                            {c.phone}
                          </td>
                          <td className="py-4 px-6 text-xs font-semibold text-slate-500 dark:text-slate-400">
                            <span className="inline-block whitespace-nowrap bg-slate-100 dark:bg-white/5 px-2 py-1 rounded border border-slate-200/50 dark:border-white/[0.08]">
                              {(c as any).payment_terms || "Net 30"}
                            </span>
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800 dark:text-slate-100">
                            <div className="flex items-center justify-end gap-1.5">
                              <span>{formatCurrency(c.credit_limit)}</span>
                              <button
                                onClick={() => handleOpenEditModal(c)}
                                className="text-slate-400 hover:text-blue-600 p-1 rounded hover:bg-slate-100 dark:hover:bg-white/5 transition-all cursor-pointer"
                                title="Edit Settings"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800 dark:text-slate-100">
                            {formatCurrency(c.outstanding_balance)}
                          </td>
                          <td className="py-4 px-6 text-center">
                            {isRisk ? (
                              <span className="inline-flex items-center gap-1 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 px-2 py-1 rounded-full text-[10px] font-bold animate-pulse">
                                <AlertTriangle className="w-3 h-3" />
                                <span>Credit At Risk</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20 px-2 py-1 rounded-full text-[10px] font-bold">
                                <CheckCircle2 className="w-3 h-3" />
                                <span>Healthy</span>
                              </span>
                            )}
                          </td>
                          <td className="py-4 px-6 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <button
                                onClick={() => handleOpenStatement(c)}
                                className="inline-flex items-center gap-1 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 px-2.5 py-1 rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-sm"
                              >
                                <span>📄 Statement</span>
                              </button>
                              <button
                                onClick={() => handleOpenPaymentHistory(c)}
                                className="inline-flex items-center gap-1 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 px-2.5 py-1 rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-sm"
                                title="Payment History"
                              >
                                <CreditCard className="w-3 h-3" />
                                <span>Payments</span>
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Pagination */}
            {!loading && !error && total > limit && (
              <div className="p-4 border-t border-dashboard-border">
                <Pagination total={total} skip={skip} limit={limit} onPageChange={handlePageChange} />
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Payment History Drawer */}
      {isPaymentDrawerOpen && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none" role="dialog" aria-modal="true" aria-labelledby="payment-drawer-title">
          <div className="w-[420px] bg-white dark:bg-dashboard-card h-screen shadow-2xl flex flex-col animate-slide-in border-l border-slate-200 dark:border-white/10 pointer-events-auto">
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 id="payment-drawer-title" className="font-bold text-base">Payment History</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">{paymentDrawerCustomer}</p>
              </div>
              <button onClick={() => setIsPaymentDrawerOpen(false)} className="p-1.5 rounded-full hover:bg-brand-darkHover transition-all cursor-pointer" aria-label="Close payment history">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {loadingPayments ? (
                [1, 2, 3].map(i => <div key={i} className="animate-pulse h-14 bg-slate-100 dark:bg-white/5 rounded-xl" />)
              ) : paymentHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-center gap-2">
                  <CreditCard className="w-8 h-8 text-slate-300" />
                  <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">No payments recorded</p>
                  <p className="text-xs text-slate-400">Payments will appear here once recorded</p>
                </div>
              ) : (
                paymentHistory.map((p: any, i: number) => (
                  <div key={i} className="p-3 rounded-xl border border-dashboard-border bg-slate-50/50 dark:bg-dashboard-inset flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-slate-700 dark:text-slate-300">{p.payment_code || p.id?.slice(0, 8)}</span>
                      <span className="text-xs font-extrabold text-emerald-700 dark:text-emerald-400">₹{Number(p.total_amount ?? p.amount ?? 0).toLocaleString("en-IN")}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                      <span>{p.method || p.payment_method || "—"}</span>
                      <span>{p.created_at ? formatDateTime(p.created_at, "date") : "—"}</span>
                    </div>
                    {p.reference_number && <p className="text-[10px] text-slate-400 font-mono truncate">Ref: {p.reference_number}</p>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Configuration Modal */}
      {isEditModalOpen && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="edit-config-modal-title">
          <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 shadow-2xl w-full max-w-md p-6 animate-scale-up relative mx-4 animate-slide-in">
            <button
              onClick={() => setIsEditModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-full hover:bg-slate-50 dark:hover:bg-white/5 transition-all cursor-pointer"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">⚙️</span>
              <h3 id="edit-config-modal-title" className="font-bold text-slate-800 dark:text-slate-100 text-lg">Configure Store Account</h3>
            </div>

            <p className="text-xs text-slate-400 font-semibold mb-6">
              Adjust parameters for <span className="text-slate-700 dark:text-slate-300 font-bold">{selectedCustomer.retailer_name}</span> ({selectedCustomer.customer_id})
            </p>

            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Credit Limit (₹)</label>
                <input
                  type="number"
                  step="1"
                  value={updatedLimit}
                  onChange={(e) => setUpdatedLimit(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold"
                  placeholder="e.g. 100000"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Billing / Payment Terms</label>
                <select
                  value={updatedTerms}
                  onChange={(e) => setUpdatedTerms(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold cursor-pointer"
                  required
                >
                  <option value="0-15 Days">0-15 Days</option>
                  <option value="16-30 Days">16-30 Days</option>
                  <option value="31-60 Days">31-60 Days</option>
                  <option value="60+ Days">60+ Days</option>
                  <option value="Net 15">Net 15</option>
                  <option value="Net 30">Net 30</option>
                  <option value="COD">COD</option>
                </select>
              </div>

              <div className="flex items-center justify-between py-2 border-t border-slate-100 dark:border-white/5 pt-4">
                <div>
                  <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">WhatsApp Notifications</label>
                  <p className="text-[10px] text-slate-400">Receive automated order updates via WhatsApp.</p>
                </div>
                <button
                  type="button"
                  onClick={toggleCustomerWhatsappPrefs}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${whatsappNotificationsEnabled ? "bg-emerald-500" : "bg-slate-300"
                    }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white dark:bg-dashboard-card shadow ring-0 transition duration-200 ease-in-out ${whatsappNotificationsEnabled ? "translate-x-5" : "translate-x-0"
                      }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-white/5 mt-6">
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 rounded-lg text-xs font-bold hover:bg-slate-50 dark:hover:bg-white/5 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingConfig}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {savingConfig ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Configuration</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Onboard New Retailer Modal */}
      {isOnboardModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="onboard-modal-title">
          <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 shadow-2xl w-full max-w-md p-6 animate-scale-up relative mx-4 animate-slide-in">
            <button
              onClick={() => {
                setIsOnboardModalOpen(false);
                setStoreName("");
                setContactNumber("");
                setDeliveryAddress("");
                setCreditLimit("100000");
                setBillingTerms("Net 30");
              }}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-full hover:bg-slate-50 dark:hover:bg-white/5 transition-all cursor-pointer"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">🏪</span>
              <h3 id="onboard-modal-title" className="font-bold text-slate-800 dark:text-slate-100 text-lg">Onboard New Retailer</h3>
            </div>

            <p className="text-xs text-slate-400 font-semibold mb-6">
              Register a new B2B customer retailer under the active tenant context.
            </p>

            <form onSubmit={handleOnboardSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Store Name</label>
                <input
                  type="text"
                  value={storeName}
                  onChange={(e) => setStoreName(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold"
                  placeholder="e.g. Kaveri Provision Store"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Contact Phone</label>
                <input
                  type="text"
                  value={contactNumber}
                  onChange={(e) => setContactNumber(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold"
                  placeholder="e.g. +919999888877"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Delivery Address</label>
                <textarea
                  value={deliveryAddress}
                  onChange={(e) => setDeliveryAddress(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold h-20 resize-none"
                  placeholder="e.g. Bengaluru, Indiranagar"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Initial Credit Ceiling Limit (₹)</label>
                <input
                  type="number"
                  step="1"
                  value={creditLimit}
                  onChange={(e) => setCreditLimit(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold"
                  placeholder="e.g. 100000"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase">Billing Terms</label>
                <select
                  value={billingTerms}
                  onChange={(e) => setBillingTerms(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card font-semibold cursor-pointer"
                  required
                >
                  <option value="0-15 Days">0-15 Days</option>
                  <option value="16-30 Days">16-30 Days</option>
                  <option value="31-60 Days">31-60 Days</option>
                  <option value="60+ Days">60+ Days</option>
                  <option value="Net 15">Net 15</option>
                  <option value="Net 30">Net 30</option>
                  <option value="COD">COD</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-white/5 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setIsOnboardModalOpen(false);
                    setStoreName("");
                    setContactNumber("");
                    setDeliveryAddress("");
                    setCreditLimit("100000");
                    setBillingTerms("Net 30");
                  }}
                  className="px-4 py-2 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 rounded-lg text-xs font-bold hover:bg-slate-50 dark:hover:bg-white/5 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingOnboard}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {savingOnboard ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Onboarding...</span>
                    </>
                  ) : (
                    <span>Onboard Retailer</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Statement Drawer Overlay */}
      {isStatementOpen && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none">
          <div className="flex-1 pointer-events-none"></div>

          <div className="w-[600px] bg-white dark:bg-dashboard-card h-screen shadow-2xl flex flex-col animate-slide-in relative border-l border-slate-200 dark:border-white/10 pointer-events-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 className="font-bold text-lg">Customer Account Statement</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">
                  Store: <span className="text-white font-bold">{statementCustomerName}</span>
                </p>
              </div>
              <button
                onClick={() => setIsStatementOpen(false)}
                className="p-1.5 rounded-full hover:bg-brand-darkHover text-brand-textMuted hover:text-white transition-all cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {loadingStatement ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Retrieving statement history...</span>
                </div>
              ) : activeStatementRows.length === 0 ? (
                <div className="text-center text-slate-400 py-12 font-medium text-xs">
                  No transaction history recorded on this account ledger.
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Summary Metric inside Statement Drawer */}
                  <div className="bg-slate-50 dark:bg-dashboard-inset p-4 rounded-xl border border-slate-200/50 dark:border-white/[0.08] flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">Current Account Balance</span>
                    <span className="text-base font-extrabold text-slate-800 dark:text-slate-100">
                      {formatCurrency(activeStatementRows[activeStatementRows.length - 1].running_balance)}
                    </span>
                  </div>

                  <div className="border border-slate-100 dark:border-white/5 rounded-xl overflow-hidden shadow-sm">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="text-slate-400 font-bold border-b border-dashboard-border bg-slate-50 dark:bg-dashboard-inset">
                          <th className="py-2.5 px-4">Date</th>
                          <th className="py-2.5 px-4">Reference</th>
                          <th className="py-2.5 px-4 text-right">Debit (+)</th>
                          <th className="py-2.5 px-4 text-right">Credit (-)</th>
                          <th className="py-2.5 px-4 text-right">Balance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-white/5 font-semibold text-slate-700 dark:text-slate-300">
                        {activeStatementRows.map((row) => (
                          <tr key={row.id} className="hover:bg-slate-50/50 dark:hover:bg-white/5">
                            <td className="py-3 px-4 text-slate-500 dark:text-slate-400 text-[10px] whitespace-nowrap">
                              {formatDateTime(row.created_at, "datetime")}
                            </td>
                            <td className="py-3 px-4 text-slate-800 dark:text-slate-100 text-[11px] font-bold">
                              {row.reference_id.startsWith("ORD-") ? `Invoice #${row.reference_id}` : `Payment ${row.reference_id}`}
                            </td>
                            <td className="py-3 px-4 text-right font-bold text-rose-600 dark:text-rose-400">
                              {row.type === "DEBIT" ? formatCurrency(row.amount) : "—"}
                            </td>
                            <td className="py-3 px-4 text-right font-bold text-emerald-600 dark:text-emerald-400">
                              {row.type === "CREDIT" ? formatCurrency(row.amount) : "—"}
                            </td>
                            <td className="py-3 px-4 text-right font-bold text-slate-800 dark:text-slate-100">
                              {formatCurrency(row.running_balance)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-dashboard-border bg-slate-50 dark:bg-dashboard-inset flex items-center justify-end">
              <button
                onClick={() => setIsStatementOpen(false)}
                className="px-5 py-2.5 bg-slate-800 text-white hover:bg-slate-700 text-xs font-bold rounded-lg transition-all cursor-pointer shadow-sm"
              >
                Close Statement
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sleek Floating Toast Notification */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 dark:bg-dashboard-card/95 backdrop-blur-md border border-slate-100 dark:border-white/5 shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-w-sm">
          {toast.type === "success" ? (
            <div className="w-8 h-8 rounded-full bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-sm">
              <CheckCircle2 className="w-4.5 h-4.5" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center text-rose-600 dark:text-rose-400 shrink-0 shadow-sm">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-slate-800 dark:text-slate-100">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 dark:hover:bg-white/5 transition-all shrink-0 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function CustomersPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center p-8 bg-dashboard-bg">Loading Customers Hub...</div>}>
      <CustomersContent />
    </Suspense>
  );
}
