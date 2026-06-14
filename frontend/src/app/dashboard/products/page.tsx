"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { Search, Loader2, RefreshCw, AlertCircle, Layers } from "lucide-react";

interface Product {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  base_price: number;
}

export default function ProductsPage() {
  const [activeTenantId, setActiveTenantId] = useState("d3b07384-d113-4956-a5d2-64be7357c11d");
  const [products, setProducts] = useState<Product[]>([]);
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

  // Fetch product catalog for active tenant
  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}`);
      if (!resp.ok) throw new Error("Failed to fetch products");
      const data = await resp.json();
      setProducts(data);
      setError(null);
    } catch (err: any) {
      console.error("Products load failed:", err);
      setError(err.message || "Failed to load products from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // Handle live catalog filtering
  const filteredProducts = products.filter(p => 
    p.sku_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.brand.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.pack_size.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2
    }).format(val);
  };

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      {/* Sidebar navigation panel */}
      <Sidebar
        activeTab="Products"
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
                <Layers className="w-5 h-5 text-brand-blue" />
                <span>Products Catalog</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Manage all product items, wholesales rates, packaging, and catalog codes
              </p>
            </div>

            <button
              onClick={fetchProducts}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Catalog</span>
            </button>
          </div>

          {/* Master Grid / Card Panel */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
            {/* Search filter utility bar */}
            <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 rounded-t-xl gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by name, brand, SKU or category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700"
                />
              </div>

              <div className="text-xs font-bold text-slate-400">
                Total Listed SKUs: <span className="text-slate-700">{filteredProducts.length}</span>
              </div>
            </div>

            {/* Catalog Grid View */}
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading catalog items...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button 
                    onClick={fetchProducts}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredProducts.length === 0 ? (
                <div className="text-center text-slate-400 py-24">
                  <p className="text-sm font-medium">No products match your search query.</p>
                  <p className="text-xs text-slate-400 mt-1">Try refining your filter parameters or verify tenant catalogs.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                      <th className="py-3 px-6">SKU ID</th>
                      <th className="py-3 px-6">Brand</th>
                      <th className="py-3 px-6">Category</th>
                      <th className="py-3 px-6">Pack Size</th>
                      <th className="py-3 px-6 text-right">Wholesale Price</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredProducts.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50/50 transition-colors group">
                        <td className="py-4 px-6 font-bold text-slate-800 text-sm">
                          {p.sku_id}
                        </td>
                        <td className="py-4 px-6 font-semibold text-slate-600">
                          {p.brand}
                        </td>
                        <td className="py-4 px-6 font-medium text-slate-500">
                          {p.category}
                        </td>
                        <td className="py-4 px-6 text-slate-600 font-semibold text-xs">
                          <span className="bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200/50">
                            {p.pack_size}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                          {formatCurrency(p.base_price)}
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
    </div>
  );
}
