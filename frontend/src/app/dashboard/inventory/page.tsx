"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Pagination from "@/components/Pagination";
import EmptyState from "@/components/EmptyState";
import { TableSkeleton } from "@/components/Skeletons";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Search, Download, AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react";

interface InventoryItem {
  id: string;
  sku: string;
  product_name: string;
  warehouse_location: string;
  quantity_on_hand: number;
  reorder_level: number;
  last_stock_check: string;
  status: "in_stock" | "low_stock" | "out_of_stock";
}

export default function InventoryPage() {
  const [tenantId, setTenantId] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "in_stock" | "low_stock" | "out_of_stock">("all");
  
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalItems, setTotalItems] = useState(0);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;

  useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) setTenantId(storedTenant);
  }, []);

  const fetchInventory = useCallback(async () => {
    if (!tenantId) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        tenant_id: tenantId,
        skip: ((currentPage - 1) * pageSize).toString(),
        limit: pageSize.toString(),
        ...(searchQuery && { search: searchQuery }),
        ...(filterStatus !== "all" && { status: filterStatus })
      });

      const response = await fetch(`${apiBase}/api/v1/inventory?${params}`, {
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` })
        }
      });

      if (response.ok) {
        const data = await response.json();
        setInventory(Array.isArray(data) ? data : data.items || []);
        setTotalItems(data.total || data.length || 0);
      } else {
        setError("Failed to load inventory");
      }
    } catch (err) {
      setError("Network error");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [tenantId, apiBase, token, currentPage, pageSize, searchQuery, filterStatus]);

  useEffect(() => {
    fetchInventory();
  }, [fetchInventory]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "in_stock":
        return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case "low_stock":
        return <AlertTriangle className="w-4 h-4 text-amber-600" />;
      case "out_of_stock":
        return <AlertCircle className="w-4 h-4 text-rose-600" />;
      default:
        return null;
    }
  };

  const totalPages = Math.ceil(totalItems / pageSize);

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Inventory" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-slate-800">Inventory</h1>
                <p className="text-xs text-slate-400 font-semibold mt-1">Real-time stock levels and warehouse management</p>
              </div>
              <button className="flex items-center gap-2 px-4 py-2 bg-white border border-dashboard-border rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors">
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>

            {/* Search & Filter */}
            <div className="flex items-center gap-3 mb-6">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by product name or SKU..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full pl-10 pr-4 py-2.5 border border-dashboard-border rounded-lg text-sm focus:ring-2 focus:ring-blue-100 focus:border-blue-500 outline-none"
                />
              </div>

              <select
                value={filterStatus}
                onChange={(e) => {
                  setFilterStatus(e.target.value as any);
                  setCurrentPage(1);
                }}
                className="px-4 py-2.5 border border-dashboard-border rounded-lg text-sm bg-white hover:bg-slate-50 cursor-pointer outline-none"
              >
                <option value="all">All Status</option>
                <option value="in_stock">In Stock</option>
                <option value="low_stock">Low Stock</option>
                <option value="out_of_stock">Out of Stock</option>
              </select>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-800">{error}</p>
                  <button onClick={fetchInventory} className="text-xs font-semibold text-rose-600 hover:text-rose-700 mt-1 underline">
                    Try again
                  </button>
                </div>
              </div>
            )}

            {loading ? (
              <TableSkeleton rows={5} />
            ) : inventory.length === 0 ? (
              <EmptyState
                title="No inventory records"
                description="Start syncing your inventory levels"
                customIcon="inventory"
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
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Location</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">On Hand</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Reorder Level</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Status</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Last Check</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dashboard-border">
                        {inventory.map((item) => (
                          <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{item.product_name}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-mono text-slate-600">{item.sku}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-600">{item.warehouse_location}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{item.quantity_on_hand} units</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-600">{item.reorder_level} units</p>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                {getStatusIcon(item.status)}
                                <span className={`text-xs font-semibold ${
                                  item.status === "in_stock" ? "text-emerald-700" :
                                  item.status === "low_stock" ? "text-amber-700" :
                                  "text-rose-700"
                                }`}>
                                  {item.status.replace("_", " ")}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-xs text-slate-500">{new Date(item.last_stock_check).toLocaleDateString()}</p>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

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
