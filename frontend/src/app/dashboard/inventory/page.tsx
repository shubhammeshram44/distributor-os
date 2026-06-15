"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { Search, Loader2, RefreshCw, AlertCircle, Box, AlertTriangle, CheckCircle2, X } from "lucide-react";

interface InventoryItem {
  id: string;
  sku_id: string;
  product_name: string;
  stock_quantity: number;
  low_stock_threshold?: number;
}

const getStockStatus = (quantity: number, threshold: number) => {
  if (quantity === 0) return { label: "Out of Stock", style: "bg-rose-50 text-rose-700 border-rose-200" };
  if (quantity < threshold) return { label: "Low Stock", style: "bg-amber-50 text-amber-700 border-amber-200" };
  return { label: "Healthy", style: "bg-emerald-50 text-emerald-700 border-emerald-200" };
};

export default function InventoryPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [skuList, setSkuList] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    sku_id: "",
    quantity_received: ""
  });
  const [submitting, setSubmitting] = useState(false);
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

  // Fetch inventory levels for active tenant
  const fetchInventory = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products/inventory?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to fetch inventory levels");
      const data = await resp.json();
      setInventory(data);
      setError(null);
    } catch (err: any) {
      console.error("Inventory load failed:", err);
      setError(err.message || "Failed to load inventory from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  // Fetch valid SKUs list for dropdown
  const fetchSkuList = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
      if (resp.ok) {
        const data = await resp.json();
        setSkuList(data.map((p: any) => p.sku_id));
      }
    } catch (err) {
      console.error("Failed to load SKUs:", err);
    }
  }, [activeTenantId]);

  useEffect(() => {
    if (!activeTenantId) return;
    setInventory([]);
    fetchInventory(activeTenantId);
    fetchSkuList(activeTenantId);
  }, [activeTenantId, fetchInventory, fetchSkuList]);


  // Handle stock inward replenishment form submit
  const handleInwardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const { sku_id, quantity_received } = formData;
    
    if (!sku_id) {
      showToast("Please select a valid SKU.", "error");
      return;
    }
    
    const qtyInt = parseInt(quantity_received);
    if (isNaN(qtyInt) || qtyInt <= 0) {
      showToast("Quantity received must be a positive number.", "error");
      return;
    }
    
    setSubmitting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products/adjust-stock?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku_id,
          quantity_received: qtyInt
        })
      });
      
      const data = await resp.json();
      if (resp.ok) {
        showToast(`Successfully replenished ${qtyInt} units of SKU ${sku_id}!`, "success");
        setFormData({ sku_id: "", quantity_received: "" });
        fetchInventory(activeTenantId); // Instantly reload stock data grid and warnings

      } else {
        const detail = data.detail || "Failed to inward stock batch.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error("Inward submit error:", err);
      showToast("Network connection breakdown during stock adjustment.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  // Handle live catalog filtering
  const filteredInventory = inventory.filter(item => 
    item.sku_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.product_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate statistics
  const lowStockCount = filteredInventory.filter(item => {
    const threshold = item.low_stock_threshold ?? 10;
    return item.stock_quantity > 0 && item.stock_quantity < threshold;
  }).length;
  const outOfStockCount = filteredInventory.filter(item => item.stock_quantity <= 0).length;
  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      {/* Sidebar navigation panel */}
      <Sidebar
        activeTab="Inventory"
        setActiveTab={() => {}}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        {/* Header containing tenant switcher */}
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {/* Headline Controls */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
                <Box className="w-5 h-5 text-brand-blue" />
                <span>Warehouse Inventory</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Track physical quantities on hand, warehouse locations, and low-stock alerts
              </p>
            </div>

            <button
              onClick={() => {
                if (activeTenantId) {
                  fetchInventory(activeTenantId);
                }
              }}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Inventory</span>
            </button>

          </div>

          {/* Quick Metrics Summary & Inward Stock Form Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Metric Cards (Takes 3/4 width) */}
            <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6 h-full">
              <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between h-full">
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Products Tracked</p>
                  <h3 className="text-2xl font-extrabold text-slate-800 mt-1">{filteredInventory.length}</h3>
                </div>
                <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100 shadow-sm">
                  <Box className="w-5 h-5" />
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between h-full">
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Low Stock SKUs</p>
                  <h3 className={`text-2xl font-extrabold mt-1 ${lowStockCount > 0 ? "text-amber-600" : "text-slate-800"}`}>
                    {lowStockCount}
                  </h3>
                </div>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border shadow-sm ${
                  lowStockCount > 0 ? "bg-amber-50 text-amber-600 border-amber-100 animate-pulse" : "bg-slate-50 text-slate-400 border-slate-100"
                }`}>
                  <AlertTriangle className="w-5 h-5" />
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between h-full">
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Out of Stock SKUs</p>
                  <h3 className={`text-2xl font-extrabold mt-1 ${outOfStockCount > 0 ? "text-rose-600" : "text-slate-800"}`}>
                    {outOfStockCount}
                  </h3>
                </div>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border shadow-sm ${
                  outOfStockCount > 0 ? "bg-rose-50 text-rose-600 border-rose-100 animate-pulse" : "bg-slate-50 text-slate-400 border-slate-100"
                }`}>
                  <AlertCircle className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Inward Stock Adjustment Widget (Takes 1/4 width) */}
            <div className="lg:col-span-1 bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between">
              <form onSubmit={handleInwardSubmit} className="space-y-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-lg">📥</span>
                  <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider">Inward Batch Arrival</h4>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-0.5">Select Product SKU</label>
                  <select
                    value={formData.sku_id}
                    onChange={(e) => setFormData(prev => ({ ...prev, sku_id: e.target.value }))}
                    className="w-full px-2 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-700 bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer"
                  >
                    <option value="">-- Choose SKU --</option>
                    {skuList.map((sku) => (
                      <option key={sku} value={sku}>
                        {sku}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-0.5">Quantity Received</label>
                  <input
                    type="number"
                    placeholder="e.g. 50"
                    value={formData.quantity_received}
                    onChange={(e) => setFormData(prev => ({ ...prev, quantity_received: e.target.value }))}
                    className="w-full px-2 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs py-2 rounded-lg transition-colors shadow-sm disabled:bg-blue-400 flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-3 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <span>Register Inbound</span>
                  )}
                </button>
              </form>
            </div>
          </div>

          {/* Master Table / Ledger Panel */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
            {/* Search filter utility bar */}
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 rounded-t-xl gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by SKU or Product name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700"
                />
              </div>

              {(lowStockCount > 0 || outOfStockCount > 0) && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 border border-amber-100 rounded-lg text-amber-700 text-xs font-semibold animate-pulse">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Attention Required: Stock levels dropping critical</span>
                </div>
              )}
            </div>

            {/* Warehouse Table Grid */}
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading inventory data...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button 
                    onClick={() => {
                      if (activeTenantId) {
                        fetchInventory(activeTenantId);
                      }
                    }}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>

                </div>
              ) : filteredInventory.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/40 text-center my-4">
                  <div className="p-3 bg-slate-100 text-slate-400 rounded-full mb-3">
                    <Box className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800">Your workspace is clean</h3>
                  <p className="text-xs text-slate-500 max-w-xs mt-1">
                    Connect your warehouse stock or send your first WhatsApp text order to see live tracking metrics update instantly.
                  </p>
                </div>
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                      <th className="py-3 px-6">SKU ID</th>
                      <th className="py-3 px-6">Product Name</th>
                      <th className="py-3 px-6 text-center">Stock Status</th>
                      <th className="py-3 px-6 text-right">Available Stock Quantity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredInventory.map((item) => {
                      const threshold = item.low_stock_threshold ?? 10;
                      const status = getStockStatus(item.stock_quantity, threshold);
                      
                      const isOutOfStock = item.stock_quantity === 0;
                      const isLowStock = item.stock_quantity > 0 && item.stock_quantity < threshold;
                      
                      let statusBadge = (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${status.style} ${isOutOfStock || isLowStock ? "animate-pulse" : ""}`}>
                          {status.label}
                        </span>
                      );
                      let qtyClass = "text-slate-800 font-extrabold";
                      
                      if (isOutOfStock) {
                        qtyClass = "text-rose-600 font-black animate-pulse";
                      } else if (isLowStock) {
                        qtyClass = "text-amber-600 font-black animate-pulse";
                      }

                      return (
                        <tr key={item.id} className="hover:bg-slate-50/50 transition-colors group">
                          <td className="py-4 px-6 font-bold text-slate-800 text-sm">
                            {item.sku_id}
                          </td>
                          <td className="py-4 px-6 font-semibold text-slate-700">
                            {item.product_name}
                          </td>
                          <td className="py-4 px-6 text-center">
                            {statusBadge}
                          </td>
                          <td className={`py-4 px-6 text-right text-sm ${qtyClass}`}>
                            {item.stock_quantity} units
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
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 transition-all shrink-0"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
