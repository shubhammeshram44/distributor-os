"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Pagination from "@/components/ui/Pagination";
import {
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  CreditCard,
  CheckCircle2,
  X,
  Plus
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

export default function CollectionsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Voucher Modal State
  const [isVoucherModalOpen, setIsVoucherModalOpen] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("CASH");
  const [amount, setAmount] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Pagination state
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 50;

  // Payment history drawer state
  const [isPaymentDrawerOpen, setIsPaymentDrawerOpen] = useState(false);
  const [paymentHistory, setPaymentHistory] = useState<any[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(false);
  const [paymentDrawerCustomer, setPaymentDrawerCustomer] = useState("");

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

  // Fetch customers sorted by outstanding balance descending (paginated)
  const fetchCustomers = useCallback(async (tenantId?: string, newSkip?: number) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    const currentSkip = newSkip !== undefined ? newSkip : skip;
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(
        `${apiBase}/api/v1/customers?tenant_id=${targetTenant}&sort_by=outstanding_balance&sort_order=desc&skip=${currentSkip}&limit=${limit}`,
        { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!resp.ok) throw new Error("Failed to fetch customer collections data");
      const data = await resp.json();
      const items = data.items ?? data;
      setCustomers(items);
      setTotal(data.total ?? items.length);
      setError(null);
    } catch (err: any) {
      console.error("Collections load failed:", err);
      setError(err.message || "Failed to load collections registry from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, skip, limit]);

  useEffect(() => {
    if (activeTenantId) {
      setCustomers([]);
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

  const handleVoucherSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId || !amount) {
      showToast("Please fill in all required fields.", "error");
      return;
    }

    const amtVal = parseFloat(amount);
    if (isNaN(amtVal) || amtVal <= 0) {
      showToast("Amount must be greater than zero.", "error");
      return;
    }

    setSubmitting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/payments/collection-voucher?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          amount: amtVal,
          method: paymentMethod,
          reference_number: referenceNumber.trim() || null
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast("Collection voucher recorded successfully!", "success");
        setIsVoucherModalOpen(false);
        // Reset form fields
        setSelectedCustomerId("");
        setAmount("");
        setReferenceNumber("");
        setPaymentMethod("CASH");
        
        // Refresh customer list
        fetchCustomers(activeTenantId);
      } else {
        const detail = data.detail || "Failed to record collection voucher.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during voucher recording.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // Filter Logic
  const filteredCustomers = customers.filter(c => {
    const query = searchQuery.toLowerCase();
    return (
      c.customer_id.toLowerCase().includes(query) ||
      c.retailer_name.toLowerCase().includes(query)
    );
  });

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      <Sidebar
        activeTab="Collections"
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
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-brand-blue" />
                <span>Collections Manager</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Record B2B invoice collection vouchers and trace client credit outstanding liabilities
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsVoucherModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm cursor-pointer animate-fade-in"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Record Collection Voucher</span>
              </button>

              <button
                onClick={() => fetchCustomers(activeTenantId)}
                className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                <span>Refresh Registry</span>
              </button>
            </div>
          </div>

          {/* Grid Layout of Debtors */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 rounded-t-xl gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by Store Name or Customer ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700 font-medium"
                />
              </div>

              <div className="text-xs font-bold text-slate-400">
                Active Debtors: <span className="text-slate-700">{total > 0 ? total : filteredCustomers.length}</span>
              </div>
            </div>

            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading collection records...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button
                    onClick={() => fetchCustomers(activeTenantId)}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredCustomers.length === 0 ? (
                <div className="text-center text-slate-400 py-24">
                  <p className="text-sm font-medium">No debtors found.</p>
                  <p className="text-xs text-slate-400 mt-1">Excellent! No active outstanding liabilities under this tenant context.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                      <th className="py-3 px-6">Customer Code</th>
                      <th className="py-3 px-6">Store Name</th>
                      <th className="py-3 px-6 text-right">Credit Limit</th>
                      <th className="py-3 px-6 text-right">Outstanding Balance</th>
                      <th className="py-3 px-6 text-center">Liability Status</th>
                      <th className="py-3 px-6 text-center">History</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredCustomers.map((c) => {
                      const percentage = c.credit_limit > 0 ? (c.outstanding_balance / c.credit_limit) * 100 : 0;
                      return (
                        <tr key={c.id} className="hover:bg-slate-50/50 transition-colors group">
                          <td className="py-4 px-6 font-bold text-slate-800 text-sm">
                            {c.customer_id}
                          </td>
                          <td className="py-4 px-6 font-bold text-slate-700">
                            <div>
                              <p className="font-bold text-slate-800 text-sm">{c.retailer_name}</p>
                              <p className="text-[10px] text-slate-400 font-semibold mt-0.5">{c.address_text}</p>
                            </div>
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                            {formatCurrency(c.credit_limit)}
                          </td>
                          <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                            <span className={c.outstanding_balance > 0 ? "text-rose-600" : "text-emerald-600"}>
                              {formatCurrency(c.outstanding_balance)}
                            </span>
                          </td>
                          <td className="py-4 px-6 text-center">
                            {c.outstanding_balance <= 0 ? (
                              <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 rounded-full text-[10px] font-bold">
                                No Liability
                              </span>
                            ) : percentage >= 90 ? (
                              <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-1 rounded-full text-[10px] font-bold animate-pulse">
                                Critical Debt
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 px-2.5 py-1 rounded-full text-[10px] font-bold">
                                Active Liability
                              </span>
                            )}
                          </td>
                          <td className="py-4 px-6 text-center">
                            <button
                              onClick={() => handleOpenPaymentHistory(c)}
                              className="inline-flex items-center gap-1 bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 px-2.5 py-1 rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-sm"
                              title="Payment History"
                            >
                              <CreditCard className="w-3 h-3" />
                              <span>Payments</span>
                            </button>
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

      {/* Payment History Side Drawer */}
      {isPaymentDrawerOpen && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none">
          <div className="w-[420px] bg-white h-screen shadow-2xl flex flex-col animate-slide-in border-l border-slate-200 pointer-events-auto">
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 className="font-bold text-base">Payment History</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">{paymentDrawerCustomer}</p>
              </div>
              <button
                onClick={() => setIsPaymentDrawerOpen(false)}
                className="p-1.5 rounded-full hover:bg-white/10 transition-all cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {loadingPayments ? (
                [1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse h-14 bg-slate-100 rounded-xl" />
                ))
              ) : paymentHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-center gap-2">
                  <CreditCard className="w-8 h-8 text-slate-300" />
                  <p className="text-sm font-semibold text-slate-500">No payments recorded</p>
                  <p className="text-xs text-slate-400">Vouchers will appear here once recorded</p>
                </div>
              ) : (
                paymentHistory.map((p: any, i: number) => (
                  <div key={i} className="p-3 rounded-xl border border-dashboard-border bg-slate-50/50 flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-slate-700">
                        {p.payment_code || p.id?.slice(0, 8)}
                      </span>
                      <span className="text-xs font-extrabold text-emerald-700">
                        ₹{Number(p.total_amount ?? p.amount ?? 0).toLocaleString("en-IN")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>{p.method || p.payment_method || "—"}</span>
                      <span>
                        {p.created_at
                          ? new Date(p.created_at).toLocaleDateString("en-IN", {
                              day: "numeric", month: "short", year: "numeric",
                            })
                          : "—"}
                      </span>
                    </div>
                    {p.reference_number && (
                      <p className="text-[10px] text-slate-400 font-mono truncate">Ref: {p.reference_number}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Record Collection Voucher Modal */}
      {isVoucherModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-md p-6 animate-scale-up relative mx-4 animate-slide-in">
            <button
              onClick={() => setIsVoucherModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-full hover:bg-slate-50 transition-all cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">💳</span>
              <h3 className="font-bold text-slate-800 text-lg">Record Collection Voucher</h3>
            </div>

            <p className="text-xs text-slate-400 font-semibold mb-6">
              Log a manual credit payment payment to adjust customer outstanding balance liability.
            </p>

            <form onSubmit={handleVoucherSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Select Customer *</label>
                <select
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold cursor-pointer"
                  required
                >
                  <option value="">-- Choose Debtor Retailer --</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.retailer_name} ({formatCurrency(c.outstanding_balance)} due)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Payment Method *</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold cursor-pointer"
                  required
                >
                  <option value="CASH">CASH</option>
                  <option value="UPI">UPI</option>
                  <option value="CHEQUE">CHEQUE</option>
                  <option value="CARD">CARD</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Amount Received (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                  placeholder="e.g. 5000.00"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Reference Number (Optional)</label>
                <input
                  type="text"
                  value={referenceNumber}
                  onChange={(e) => setReferenceNumber(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                  placeholder="e.g. Cheque No / UPI Txn ID"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
                <button
                  type="button"
                  onClick={() => setIsVoucherModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Recording...</span>
                    </>
                  ) : (
                    <span>Submit Voucher</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
