"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Pagination from "@/components/Pagination";
import EmptyState from "@/components/EmptyState";
import { TableSkeleton } from "@/components/Skeletons";
import ErrorBoundary from "@/components/ErrorBoundary";
import {
  Search,
  Download,
  Plus,
  ChevronRight,
  AlertCircle,
  Package,
  Tag
} from "lucide-react";

interface Product {
  id: string;
  name: string;
  sku: string;
  category: string;
  brand: string;
  unit_price: number;
  stock_quantity: number;
  pack_size: string;
  status: "active" | "inactive";
  created_at: string;
}

export default function ProductsPage() {
  const [tenantId, setTenantId] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalItems, setTotalItems] = useState(0);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;

  useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) {
      setTenantId(storedTenant);
    }
  }, []);

  const fetchProducts = useCallback(async () => {
    if (!tenantId) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        tenant_id: tenantId,
        skip: ((currentPage - 1) * pageSize).toString(),
        limit: pageSize.toString(),
        ...(searchQuery && { search: searchQuery }),
        ...(filterCategory !== "all" && { category: filterCategory })
      });

      const response = await fetch(`${apiBase}/api/v1/products?${params}`, {
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` })
        }
      });

      if (response.ok) {
        const data = await response.json();
        setProducts(Array.isArray(data) ? data : data.items || []);
        setTotalItems(data.total || data.length || 0);
      } else {
        setError("Failed to load products");
      }
    } catch (err) {
      setError("Network error while loading products");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [tenantId, apiBase, token, currentPage, pageSize, searchQuery, filterCategory]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleExport = async () => {
    try {
      const response = await fetch(
        `${apiBase}/api/v1/products/export?tenant_id=${tenantId}`,
        {
          credentials: "include",
          headers: token ? { "Authorization": `Bearer ${token}` } : {}
        }
      );

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `products-${new Date().toISOString().split("T")[0]}.csv`;
        a.click();
      }
    } catch (err) {
      console.error("Export failed:", err);
    }
  };

  const totalPages = Math.ceil(totalItems / pageSize);

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Products" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-slate-800">Products</h1>
                <p className="text-xs text-slate-400 font-semibold mt-1">Manage your product catalog</p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleExport}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-dashboard-border rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export
                </button>
                <button className="flex items-center gap-2 px-4 py-2 bg-brand-blue text-white rounded-lg text-sm font-semibold hover:bg-brand-blueHover transition-colors">
                  <Plus className="w-4 h-4" />
                  Add Product
                </button>
              </div>
            </div>

            {/* Search & Filter */}
            <div className="flex items-center gap-3 mb-6">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by product name, SKU, or brand..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full pl-10 pr-4 py-2.5 border border-dashboard-border rounded-lg text-sm focus:ring-2 focus:ring-blue-100 focus:border-blue-500 outline-none"
                />
              </div>

              <select
                value={filterCategory}
                onChange={(e) => {
                  setFilterCategory(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-4 py-2.5 border border-dashboard-border rounded-lg text-sm bg-white hover:bg-slate-50 cursor-pointer outline-none"
              >
                <option value="all">All Categories</option>
                <option value="Electronics">Electronics</option>
                <option value="Grocery">Grocery</option>
                <option value="Apparel">Apparel</option>
              </select>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-800">{error}</p>
                  <button
                    onClick={fetchProducts}
                    className="text-xs font-semibold text-rose-600 hover:text-rose-700 mt-1 underline"
                  >
                    Try again
                  </button>
                </div>
              </div>
            )}

            {/* Table */}
            {loading ? (
              <TableSkeleton rows={5} />
            ) : products.length === 0 ? (
              <EmptyState
                title="No products found"
                description="Start by adding your first product to the catalog"
                customIcon="products"
              />
            ) : (
              <>
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="border-b border-dashboard-border bg-slate-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Product</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">SKU</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Category</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Price</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Stock</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Status</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dashboard-border">
                        {products.map((product) => (
                          <tr key={product.id} className="hover:bg-slate-50 transition-colors">
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                                  <Package className="w-5 h-5 text-slate-400" />
                                </div>
                                <div>
                                  <p className="text-sm font-semibold text-slate-800">{product.name}</p>
                                  <p className="text-xs text-slate-500">{product.brand}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-mono font-semibold text-slate-600">{product.sku}</p>
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-flex items-center gap-2 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold">
                                <Tag className="w-3 h-3" />
                                {product.category}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">₹{product.unit_price.toLocaleString("en-IN")}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{product.stock_quantity}</p>
                              <p className="text-xs text-slate-500">{product.pack_size}</p>
                            </td>
                            <td className="px-6 py-4">
                              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                                product.status === "active"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : "bg-slate-100 text-slate-600"
                              }`}>
                                {product.status}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <button
                                className="text-slate-600 hover:text-slate-800 p-1 rounded hover:bg-slate-100 transition-colors"
                                title="View details"
                              >
                                <ChevronRight className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Pagination */}
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={setCurrentPage}
                  pageSize={pageSize}
                  onPageSizeChange={(size) => {
                    setPageSize(size);
                    setCurrentPage(1);
                  }}
                  totalItems={totalItems}
                />
              </>
            )}
          </main>
        </div>
      </div>
    </ErrorBoundary>
  );
}
