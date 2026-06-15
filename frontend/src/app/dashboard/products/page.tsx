"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import CatalogIngestion from "@/components/CatalogIngestion";
import { Search, Loader2, RefreshCw, AlertCircle, Layers, CheckCircle2, X } from "lucide-react";

interface Product {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  base_price: number;
}

export default function ProductsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    sku_id: "",
    brand: "",
    category: "",
    pack_size: "",
    base_price: ""
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

  // Fetch product catalog for active tenant
  const fetchProducts = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
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
    if (!activeTenantId) return;
    setProducts([]);
    fetchProducts(activeTenantId);
  }, [activeTenantId, fetchProducts]);


  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const { sku_id, brand, category, pack_size, base_price } = formData;
    
    // Validations
    if (!sku_id.trim() || !brand.trim() || !category.trim() || !pack_size.trim() || !base_price.trim()) {
      showToast("All fields are required.", "error");
      return;
    }
    
    const priceFloat = parseFloat(base_price);
    if (isNaN(priceFloat) || priceFloat < 0) {
      showToast("Wholesale Price must be a positive number.", "error");
      return;
    }
    
    setSubmitting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku_id: sku_id.trim(),
          brand: brand.trim(),
          category: category.trim(),
          pack_size: pack_size.trim(),
          base_price: priceFloat
        })
      });
      
      const data = await resp.json();
      if (resp.ok) {
        showToast("Product added successfully!", "success");
        setFormData({
          sku_id: "",
          brand: "",
          category: "",
          pack_size: "",
          base_price: ""
        });
        fetchProducts(activeTenantId); // Refresh local list

      } else {
        const detail = data.detail || "Failed to add product manually.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network connection breakdown during product creation.", "error");
    } finally {
      setSubmitting(false);
    }
  };

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
              onClick={() => {
                if (activeTenantId) {
                  fetchProducts(activeTenantId);
                }
              }}
              className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh Catalog</span>
            </button>

          </div>

          {/* Top Ingestion & Creation Split Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column: Bulk Ingestion */}
            <CatalogIngestion
              activeTenantId={activeTenantId}
              onSuccess={(msg) => {
                showToast(msg, "success");
                fetchProducts(activeTenantId);
              }}
              onError={(msg) => showToast(msg, "error")}
            />

            {/* Right Column: Manual Entry Form */}
            <div className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xl">✍️</span>
                  <h3 className="font-semibold text-slate-800 text-lg">Add Product Manually</h3>
                </div>
                
                <form onSubmit={handleManualSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-500 mb-1">SKU ID</label>
                      <input
                        type="text"
                        placeholder="e.g. PROD-HUL-SOAP"
                        value={formData.sku_id}
                        onChange={(e) => setFormData(prev => ({ ...prev, sku_id: e.target.value }))}
                        className="w-full p-2 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-slate-500 mb-1">Brand</label>
                      <input
                        type="text"
                        placeholder="e.g. HUL"
                        value={formData.brand}
                        onChange={(e) => setFormData(prev => ({ ...prev, brand: e.target.value }))}
                        className="w-full p-2 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="col-span-1">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Category</label>
                      <input
                        type="text"
                        placeholder="e.g. Soap"
                        value={formData.category}
                        onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                        className="w-full p-2 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                      />
                    </div>

                    <div className="col-span-1">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Pack Size</label>
                      <input
                        type="text"
                        placeholder="e.g. 100g"
                        value={formData.pack_size}
                        onChange={(e) => setFormData(prev => ({ ...prev, pack_size: e.target.value }))}
                        className="w-full p-2 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                      />
                    </div>

                    <div className="col-span-1">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Wholesale Price</label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="e.g. 45.00"
                        value={formData.base_price}
                        onChange={(e) => setFormData(prev => ({ ...prev, base_price: e.target.value }))}
                        className="w-full p-2 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm p-2.5 rounded-lg transition-colors shadow-sm disabled:bg-blue-400 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Adding Product...</span>
                      </>
                    ) : (
                      <span>Create Product SKU</span>
                    )}
                  </button>
                </form>
              </div>
            </div>
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
                    onClick={() => {
                      if (activeTenantId) {
                        fetchProducts(activeTenantId);
                      }
                    }}
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
