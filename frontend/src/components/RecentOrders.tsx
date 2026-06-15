"use client";

import React, { useState, useEffect } from "react";
import { MessageSquare, Globe, X, FileSpreadsheet, Loader2, ArrowRight, AlertCircle, ShoppingBag } from "lucide-react";
import { RecentOrder, OrderDetail } from "@/hooks/useDashboardData";
import Link from "next/link";

interface RecentOrdersProps {
  orders: RecentOrder[];
  fetchOrderDetails: (id: string) => Promise<void>;
  selectedOrderDetails: OrderDetail[] | null;
  loadingDetails: boolean;
  closeDetails: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
  activeTenantId?: string;
  viewAllHref?: string;
}

export default function RecentOrders({
  orders,
  fetchOrderDetails,
  selectedOrderDetails,
  loadingDetails,
  closeDetails,
  onSuccess,
  onError,
  activeTenantId,
  viewAllHref
}: RecentOrdersProps) {
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [selectedOrderNo, setSelectedOrderNo] = useState<string>("");
  const [isConfirming, setIsConfirming] = useState(false);

  const [productsList, setProductsList] = useState<any[]>([]);
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null);

  const tenantId = activeTenantId || "";

  useEffect(() => {
    const fetchProducts = async () => {
      if (!tenantId) return;
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${apiBase}/api/v1/products?tenant_id=${tenantId}`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setProductsList(data);
        }
      } catch (err) {
        console.error("Failed to load products list for resolution drawer:", err);
      }
    };
    fetchProducts();
  }, [tenantId]);

  const handleResolveItem = async (itemId: string, skuCode: string, quantity: number) => {
    setResolvingItemId(itemId);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/items/${itemId}/resolve`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_code: skuCode, quantity })
      });
      const data = await response.json();
      if (response.ok) {
        onSuccess("Order line item manually resolved successfully!");
        handleClose();
      } else {
        const errorDetail = data.detail || "Failed to resolve order item.";
        onError(errorDetail);
      }
    } catch (err) {
      onError("Network connection breakdown during order item resolution.");
    } finally {
      setResolvingItemId(null);
    }
  };

  const selectedOrder = orders.find(o => o.id === selectedOrderId);

  const handleConfirmOrder = async () => {
    if (!selectedOrderId) return;
    setIsConfirming(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/status`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to_status: "Confirmed" })
      });
      const data = await response.json();
      if (response.ok) {
        onSuccess("Order status updated to Confirmed successfully!");
        handleClose();
      } else {
        const errorDetail = data.detail || "Failed to confirm order.";
        onError(errorDetail);
      }
    } catch (err) {
      onError("Network connection breakdown during order confirmation.");
    } finally {
      setIsConfirming(false);
    }
  };

  const handleClose = () => {
    setSelectedOrderId(null);
    closeDetails();
  };

  const handleOrderIdClick = async (order: RecentOrder) => {
    setSelectedOrderId(order.id);
    setSelectedOrderNo(order.order_id);
    await fetchOrderDetails(order.id);
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  return (
    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col h-full">
      {/* Table Header */}
      <div className="flex items-center justify-between pb-4 border-b border-dashboard-border mb-4">
        <h3 className="font-bold text-slate-800 text-base">Recent Orders</h3>
        {viewAllHref ? (
          <Link href={viewAllHref} className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View all</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        ) : (
          <button className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View all</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Grid Table */}
      <div className="flex-1 overflow-x-auto flex flex-col justify-center">
        {orders && orders.length > 0 ? (
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                <th className="py-3 px-4">Order ID</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4 text-center">Channel</th>
                <th className="py-3 px-4 text-right">Amount</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4">Created On</th>
                <th className="py-3 px-4">ETA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-slate-50/70 transition-colors group">
                  <td className="py-3.5 px-4 font-semibold text-brand-blue hover:text-brand-blueHover">
                    <button
                      onClick={() => handleOrderIdClick(order)}
                      className="hover:underline text-left text-sm cursor-pointer focus:outline-none"
                    >
                      {order.order_id}
                    </button>
                  </td>
                  <td className="py-3.5 px-4 font-medium text-slate-700 max-w-[180px] truncate">
                    {order.customer}
                  </td>
                  <td className="py-3.5 px-4 text-center">
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
                  <td className="py-3.5 px-4 text-right font-bold text-slate-800">
                    {formatCurrency(order.amount)}
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none ${
                      order.status === "Confirmed"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}>
                      {order.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-xs font-semibold text-slate-500">
                    {order.created_on || order.eta}
                  </td>
                  <td className="py-3.5 px-4 text-xs font-semibold text-slate-500">
                    {order.eta}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-50 flex items-center justify-center mb-3 text-slate-400">
              <ShoppingBag className="w-6 h-6" />
            </div>
            <p className="text-sm font-semibold text-slate-600">No recent orders found</p>
            <p className="text-xs text-slate-400 mt-1 max-w-[250px]">
              Orders received via WhatsApp or the portal will populate here.
            </p>
          </div>
        )}
      </div>

      {/* Slide-out Sidebar Drawer for Line Item Details */}
      {selectedOrderId && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none">
          {/* Transparent Backdrop that lets clicks pass through to the dashboard */}
          <div className="flex-1 pointer-events-none"></div>

          {/* Drawer Content */}
          <div className="w-[500px] bg-white h-screen shadow-2xl flex flex-col animate-slide-in relative border-l border-slate-200 pointer-events-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 className="font-bold text-lg">Order Details</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">ID: {selectedOrderNo}</p>
              </div>
              <button
                onClick={handleClose}
                className="p-1.5 rounded-full hover:bg-brand-darkHover text-brand-textMuted hover:text-white transition-all"
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

            {/* Close footer button */}
            <div className="p-6 border-t border-dashboard-border bg-slate-50 flex items-center justify-between">
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
                onClick={handleClose}
                className="px-5 py-2.5 bg-slate-800 text-white hover:bg-slate-700 text-sm font-bold rounded-lg transition-all"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
