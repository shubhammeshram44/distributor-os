"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Pagination from "@/components/Pagination";
import EmptyState from "@/components/EmptyState";
import { TableSkeleton } from "@/components/Skeletons";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Search, Download, AlertCircle, Truck, MapPin } from "lucide-react";

interface Shipment {
  id: string;
  order_id: string;
  tracking_number: string;
  carrier: string;
  status: "pending" | "in_transit" | "delivered" | "failed";
  origin: string;
  destination: string;
  eta: string;
  created_at: string;
}

export default function ShipmentsPage() {
  const [tenantId, setTenantId] = useState("");
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalItems, setTotalItems] = useState(0);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;

  useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) setTenantId(storedTenant);
  }, []);

  const fetchShipments = useCallback(async () => {
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

      const response = await fetch(`${apiBase}/api/v1/shipments?${params}`, {
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` })
        }
      });

      if (response.ok) {
        const data = await response.json();
        setShipments(Array.isArray(data) ? data : data.items || []);
        setTotalItems(data.total || data.length || 0);
      } else {
        setError("Failed to load shipments");
      }
    } catch (err) {
      setError("Network error");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [tenantId, apiBase, token, currentPage, pageSize, searchQuery, filterStatus]);

  useEffect(() => {
    fetchShipments();
  }, [fetchShipments]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-slate-100 text-slate-700";
      case "in_transit":
        return "bg-blue-100 text-blue-700";
      case "delivered":
        return "bg-emerald-100 text-emerald-700";
      case "failed":
        return "bg-rose-100 text-rose-700";
      default:
        return "bg-slate-100 text-slate-700";
    }
  };

  const totalPages = Math.ceil(totalItems / pageSize);

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Shipments" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-slate-800">Shipments</h1>
                <p className="text-xs text-slate-400 font-semibold mt-1">Track deliveries and manage logistics</p>
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
                  placeholder="Search by order ID, tracking number..."
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
                  setFilterStatus(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-4 py-2.5 border border-dashboard-border rounded-lg text-sm bg-white hover:bg-slate-50 cursor-pointer outline-none"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="in_transit">In Transit</option>
                <option value="delivered">Delivered</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-800">{error}</p>
                  <button onClick={fetchShipments} className="text-xs font-semibold text-rose-600 hover:text-rose-700 mt-1 underline">
                    Try again
                  </button>
                </div>
              </div>
            )}

            {loading ? (
              <TableSkeleton rows={5} />
            ) : shipments.length === 0 ? (
              <EmptyState
                title="No shipments yet"
                description="Your shipments will appear here once orders are dispatched"
                customIcon="shipments"
              />
            ) : (
              <>
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="border-b border-dashboard-border bg-slate-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Order ID</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Tracking</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Carrier</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Route</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">ETA</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dashboard-border">
                        {shipments.map((shipment) => (
                          <tr key={shipment.id} className="hover:bg-slate-50 transition-colors">
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{shipment.order_id}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-mono text-slate-600">{shipment.tracking_number}</p>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                <Truck className="w-4 h-4 text-slate-400" />
                                <span className="text-sm text-slate-600">{shipment.carrier}</span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                                <span className="text-xs text-slate-600">{shipment.origin} → {shipment.destination}</span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-600">{new Date(shipment.eta).toLocaleDateString()}</p>
                            </td>
                            <td className="px-6 py-4">
                              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${getStatusColor(shipment.status)}`}>
                                {shipment.status.replace("_", " ")}
                              </span>
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
