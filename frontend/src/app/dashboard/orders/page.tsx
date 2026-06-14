"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  X,
  MessageSquare,
  Globe,
  FileSpreadsheet,
  ChevronRight,
  SlidersHorizontal,
  ChevronDown
} from "lucide-react";

interface OrderItem {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface OrderRow {
  id: string;
  order_id: string;
  customer: string;
  channel: string;
  amount: number;
  status: string;
  created_on: string;
  eta: string;
}

export default function OrdersPage() {
  const [activeTenantId, setActiveTenantId] = useState("d3b07384-d113-4956-a5d2-64be7357c11d");
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<"All" | "Pending" | "Confirmed" | "Needs Review">("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drawer States
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [selectedOrderNo, setSelectedOrderNo] = useState<string>("");
  const [selectedOrderDetails, setSelectedOrderDetails] = useState<OrderItem[] | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [productsList, setProductsList] = useState<any[]>([]);
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null);

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

  // Fetch all orders for active tenant
  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/orders?tenant_id=${activeTenantId}`);
      if (!resp.ok) throw new Error("Failed to fetch orders");
      const data = await resp.json();
      setOrders(data);
      setError(null);
    } catch (err: any) {
      console.error("Orders load failed:", err);
      setError(err.message || "Failed to load orders from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  // Fetch products for resolving dropdowns
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}`);
        if (res.ok) {
          const data = await res.json();
          setProductsList(data);
        }
      } catch (err) {
        console.error("Failed to load products list for resolution drawer:", err);
      }
    };
    fetchProducts();
  }, [activeTenantId]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const fetchOrderDetails = async (orderId: string) => {
    setLoadingDetails(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/dashboard/order-details/${orderId}`);
      if (!resp.ok) throw new Error("Failed to load order line item details");
      const data = await resp.json();
      setSelectedOrderDetails(data);
    } catch (err: any) {
      console.error(err);
      showToast("Failed to load order details.", "error");
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleOrderIdClick = async (order: OrderRow) => {
    setSelectedOrderId(order.id);
    setSelectedOrderNo(order.order_id);
    await fetchOrderDetails(order.id);
  };

  const handleCloseDetails = () => {
    setSelectedOrderId(null);
    setSelectedOrderDetails(null);
  };

  const handleConfirmOrder = async () => {
    if (!selectedOrderId) return;
    setIsConfirming(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to_status: "Confirmed" })
      });
      const data = await response.json();
      if (response.ok) {
        showToast("Order status updated to Confirmed successfully!", "success");
        handleCloseDetails();
        fetchOrders();
      } else {
        const errorDetail = data.detail || "Failed to confirm order.";
        showToast(errorDetail, "error");
      }
    } catch (err) {
      showToast("Network connection breakdown during order confirmation.", "error");
    } finally {
      setIsConfirming(false);
    }
  };

  const handleResolveItem = async (itemId: string, skuCode: string, quantity: number) => {
    setResolvingItemId(itemId);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/items/${itemId}/resolve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_code: skuCode, quantity })
      });
      const data = await response.json();
      if (response.ok) {
        showToast("Order line item manually resolved successfully!", "success");
        handleCloseDetails();
        fetchOrders();
      } else {
        const errorDetail = data.detail || "Failed to resolve order item.";
        showToast(errorDetail, "error");
      }
    } catch (err) {
      showToast("Network connection breakdown during order item resolution.", "error");
    } finally {
      setResolvingItemId(null);
    }
  };

  const selectedOrder = orders.find(o => o.id === selectedOrderId);

  // Status Filter Counts
  const countAll = orders.length;
  const countPending = orders.filter(o => o.status === "Pending").length;
  const countConfirmed = orders.filter(o => o.status === "Confirmed").length;
  const countNeedsReview = orders.filter(o => o.status === "Needs Review").length;

  // Filter and Search Logic
  const filteredOrders = orders.filter(o => {
    const matchesStatus = selectedStatus === "All" || o.status === selectedStatus;
    const matchesSearch =
      o.order_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.customer.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

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
        activeTab="Orders"
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
              <h1 className="text-xl font-bold text-slate-800 tracking-tight">Order Management</h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Monitor and process orders from all sales channels (WhatsApp, B2B Portal)
              </p>
            </div>

            <button
              onClick={fetchOrders}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Orders</span>
            </button>
          </div>

          {/* Status Navigation & Search Bar Card */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Tab Filters */}
            <div className="flex flex-wrap items-center gap-1 bg-slate-100/80 p-1 rounded-xl">
              <button
                onClick={() => setSelectedStatus("All")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedStatus === "All"
                    ? "bg-white text-brand-blue shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <span>All</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "All" ? "bg-blue-50 text-brand-blue" : "bg-slate-200 text-slate-600"}`}>
                  {countAll}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Pending")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedStatus === "Pending"
                    ? "bg-white text-brand-blue shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <span>Pending</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Pending" ? "bg-amber-50 text-amber-700" : "bg-slate-200 text-slate-600"}`}>
                  {countPending}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Confirmed")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedStatus === "Confirmed"
                    ? "bg-white text-brand-blue shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <span>Confirmed</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Confirmed" ? "bg-emerald-50 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>
                  {countConfirmed}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Needs Review")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedStatus === "Needs Review"
                    ? "bg-white text-brand-blue shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <span>Needs Review</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Needs Review" ? "bg-rose-50 text-rose-700" : "bg-slate-200 text-slate-600"}`}>
                  {countNeedsReview}
                </span>
              </button>
            </div>

            {/* Search input */}
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search order ID or retailer..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue text-slate-700 font-semibold"
              />
            </div>
          </div>

          {/* Master Orders Data Grid */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm overflow-hidden flex flex-col min-h-[400px]">
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading orders catalog...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button
                    onClick={fetchOrders}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredOrders.length === 0 ? (
                <div className="text-center text-slate-400 py-24">
                  <p className="text-sm font-medium">No orders match your filter criteria.</p>
                  <p className="text-xs text-slate-400 mt-1">Try changing your search query or selecting a different status filter.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                      <th className="py-3 px-6">Order ID</th>
                      <th className="py-3 px-6">Customer</th>
                      <th className="py-3 px-6 text-center">Channel</th>
                      <th className="py-3 px-6 text-right">Amount</th>
                      <th className="py-3 px-6 text-center">Status</th>
                      <th className="py-3 px-6">Created On</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredOrders.map((order) => (
                      <tr key={order.id} className="hover:bg-slate-50/70 transition-colors group">
                        <td className="py-4 px-6 font-bold text-brand-blue hover:underline">
                          <button
                            onClick={() => handleOrderIdClick(order)}
                            className="cursor-pointer font-bold text-left focus:outline-none"
                          >
                            {order.order_id}
                          </button>
                        </td>
                        <td className="py-4 px-6 font-semibold text-slate-700">
                          {order.customer}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <div className="flex items-center justify-center">
                            {order.channel.toLowerCase() === "whatsapp" ? (
                              <div className="w-7 h-7 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600 shadow-sm" title="WhatsApp Channel">
                                <MessageSquare className="w-4 h-4" />
                              </div>
                            ) : (
                              <div className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 shadow-sm" title="Portal Channel">
                                <Globe className="w-4 h-4" />
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                          {formatCurrency(order.amount)}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none ${
                            order.status === "Confirmed"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : order.status === "Needs Review"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : "bg-amber-50 text-amber-700 border border-amber-200"
                          }`}>
                            {order.status}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-xs font-semibold text-slate-500">
                          {order.created_on}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <button
                            onClick={() => handleOrderIdClick(order)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-brand-blue hover:text-brand-blueHover cursor-pointer"
                          >
                            <span>Details</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </main>
      </div>

      {/* Details Side Panel Drawer */}
      {selectedOrderId && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none">
          <div className="flex-1 pointer-events-none"></div>

          <div className="w-[500px] bg-white h-screen shadow-2xl flex flex-col animate-slide-in relative border-l border-slate-200 pointer-events-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 className="font-bold text-lg">Order Details</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">ID: {selectedOrderNo}</p>
              </div>
              <button
                onClick={handleCloseDetails}
                className="p-1.5 rounded-full hover:bg-brand-darkHover text-brand-textMuted hover:text-white transition-all cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Line Items Container */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {loadingDetails ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading line items...</span>
                </div>
              ) : selectedOrderDetails ? (
                <>
                  <h4 className="font-bold text-slate-800 text-sm border-b pb-2 mb-3">Line Items</h4>
                  {selectedOrderDetails.map((item, idx) => {
                    const isUnmatched = item.sku_id === "UNMATCHED_SKU";
                    return (
                      <div key={idx} className="p-4 rounded-xl border border-dashboard-border bg-slate-50/50 flex flex-col justify-between gap-2">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 pr-4">
                            {isUnmatched ? (
                              <div className="space-y-2">
                                <p className="font-bold text-sm text-rose-600 flex items-center gap-1.5 animate-pulse">
                                  <AlertCircle className="w-4 h-4 shrink-0" />
                                  <span>Unmatched Line Item</span>
                                </p>
                                <p className="text-[11px] text-slate-400 font-semibold mb-1">
                                  Original Text: <span className="italic">"{item.brand} SKU"</span>
                                </p>
                                <label className="block text-[10px] font-bold text-slate-400 uppercase">Map to Catalog SKU</label>
                                <select
                                  disabled={resolvingItemId === item.id}
                                  onChange={(e) => {
                                    if (e.target.value) {
                                      handleResolveItem(item.id, e.target.value, item.quantity);
                                    }
                                  }}
                                  className="w-full mt-1 p-2 border border-rose-200 rounded-lg text-xs bg-white text-slate-700 font-semibold focus:outline-none focus:ring-1 focus:ring-rose-500 cursor-pointer animate-pulse"
                                >
                                  <option value="">-- Select SKU --</option>
                                  {productsList.map((p) => (
                                    <option key={p.id} value={p.sku_id}>
                                      {p.sku_id} - {p.brand} {p.category} ({p.pack_size})
                                    </option>
                                  ))}
                                </select>
                              </div>
                            ) : (
                              <>
                                <p className="font-bold text-sm text-slate-800">{item.brand} SKU</p>
                                <p className="text-xs text-slate-400 font-semibold">{item.sku_id} ({item.pack_size})</p>
                              </>
                            )}
                          </div>
                          <div className="flex flex-col items-end shrink-0">
                            <span className="text-xs font-bold text-slate-500">Qty: {item.quantity}</span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-2 mt-1">
                          <span className="text-xs text-slate-400">Rate: {formatCurrency(item.unit_price)}</span>
                          <span className="text-sm font-bold text-slate-800">{formatCurrency(item.total_price)}</span>
                        </div>
                      </div>
                    );
                  })}

                  {/* Financial Summary */}
                  <div className="border-t border-slate-200 pt-4 mt-6 space-y-2 text-sm">
                    <div className="flex justify-between text-slate-500 font-medium">
                      <span>Subtotal</span>
                      <span>{formatCurrency(selectedOrderDetails.reduce((a, b) => a + b.total_price, 0) / 1.18)}</span>
                    </div>
                    <div className="flex justify-between text-slate-500 font-medium">
                      <span>GST (18%)</span>
                      <span>{formatCurrency(selectedOrderDetails.reduce((a, b) => a + b.total_price, 0) * 0.18 / 1.18)}</span>
                    </div>
                    <div className="flex justify-between text-base font-extrabold text-slate-800 pt-2 border-t border-dashed">
                      <span>Total Amount</span>
                      <span>{formatCurrency(selectedOrderDetails.reduce((a, b) => a + b.total_price, 0))}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-slate-400 py-12">No details available.</div>
              )}
            </div>

            {/* Footer Buttons */}
            <div className="p-6 border-t border-dashboard-border bg-slate-50 flex items-center justify-between gap-3">
              {selectedOrder && selectedOrder.status === "Pending" ? (
                <button
                  onClick={handleConfirmOrder}
                  disabled={isConfirming}
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 cursor-pointer"
                >
                  {isConfirming ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Confirming...</span>
                    </>
                  ) : (
                    <span>Confirm Order</span>
                  )}
                </button>
              ) : selectedOrder && selectedOrder.status === "Confirmed" ? (
                <button
                  onClick={() => {
                    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
                    window.open(`${apiBase}/api/v1/orders/${selectedOrderId}/invoice`, "_blank");
                  }}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 cursor-pointer"
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Download B2B Invoice</span>
                </button>
              ) : (
                <div></div>
              )}
              <button
                onClick={handleCloseDetails}
                className="px-5 py-2.5 bg-slate-800 text-white hover:bg-slate-700 text-sm font-bold rounded-lg transition-all cursor-pointer"
              >
                Close Details
              </button>
            </div>
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
