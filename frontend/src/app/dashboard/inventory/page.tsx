"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { Search, Loader2, RefreshCw, AlertCircle, Box, AlertTriangle } from "lucide-react";

interface InventoryItem {
  id: string;
  sku_id: string;
  product_name: string;
  stock_quantity: number;
}

export default function InventoryPage() {
  const [activeTenantId, setActiveTenantId] = useState("d3b07384-d113-4956-a5d2-64be7357c11d");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Fetch inventory levels for active tenant
  const fetchInventory = useCallback(async () => {
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products/inventory?tenant_id=${activeTenantId}`);
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

  useEffect(() => {
    fetchInventory();
  }, [fetchInventory]);

  // Handle live catalog filtering
  const filteredInventory = inventory.filter(item => 
    item.sku_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.product_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate statistics
  const lowStockCount = filteredInventory.filter(item => item.stock_quantity > 0 && item.stock_quantity < 10).length;
  const outOfStockCount = filteredInventory.filter(item => item.stock_quantity <= 0).length;

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
              onClick={fetchInventory}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Inventory</span>
            </button>
          </div>

          {/* Quick Metrics Summary Widgets */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Products tracked</p>
                <h3 className="text-2xl font-extrabold text-slate-800 mt-1">{filteredInventory.length}</h3>
              </div>
              <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100">
                <Box className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Low Stock SKUs</p>
                <h3 className={`text-2xl font-extrabold mt-1 ${lowStockCount > 0 ? "text-amber-600" : "text-slate-800"}`}>
                  {lowStockCount}
                </h3>
              </div>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center border ${
                lowStockCount > 0 ? "bg-amber-50 text-amber-600 border-amber-100 animate-pulse" : "bg-slate-50 text-slate-400 border-slate-100"
              }`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Out of Stock SKUs</p>
                <h3 className={`text-2xl font-extrabold mt-1 ${outOfStockCount > 0 ? "text-rose-600" : "text-slate-800"}`}>
                  {outOfStockCount}
                </h3>
              </div>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center border ${
                outOfStockCount > 0 ? "bg-rose-50 text-rose-600 border-rose-100 animate-pulse" : "bg-slate-50 text-slate-400 border-slate-100"
              }`}>
                <AlertCircle className="w-5 h-5" />
              </div>
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
                    onClick={fetchInventory}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredInventory.length === 0 ? (
                <div className="text-center text-slate-400 py-24">
                  <p className="text-sm font-medium">No items match search filter criteria.</p>
                  <p className="text-xs text-slate-400 mt-1">Try refining search parameters or sync catalog.</p>
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
                      // Color-coding thresholds
                      const isOutOfStock = item.stock_quantity <= 0;
                      const isLowStock = item.stock_quantity > 0 && item.stock_quantity < 10;
                      
                      let statusBadge = (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-100">
                          Healthy
                        </span>
                      );
                      let qtyClass = "text-slate-800 font-extrabold";
                      
                      if (isOutOfStock) {
                        statusBadge = (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-rose-50 text-rose-700 border border-rose-100 animate-pulse">
                            Out of Stock
                          </span>
                        );
                        qtyClass = "text-rose-600 font-black animate-pulse";
                      } else if (isLowStock) {
                        statusBadge = (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-50 text-amber-700 border border-amber-100 animate-pulse">
                            Low Stock Alert
                          </span>
                        );
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
    </div>
  );
}
