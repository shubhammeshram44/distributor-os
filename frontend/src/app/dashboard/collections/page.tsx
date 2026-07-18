"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Pagination from "@/components/Pagination";
import EmptyState from "@/components/EmptyState";
import { TableSkeleton, ChartSkeleton } from "@/components/Skeletons";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Search, Download, AlertCircle, TrendingDown, Calendar } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface CollectionData {
  id: string;
  customer_name: string;
  outstanding_amount: number;
  days_overdue: number;
  last_payment_date: string;
  status: "not_due" | "due" | "overdue_30" | "overdue_60" | "overdue_90";
}

export default function CollectionsPage() {
  const [tenantId, setTenantId] = useState("");
  const [collections, setCollections] = useState<CollectionData[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalItems, setTotalItems] = useState(0);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;

  useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) setTenantId(storedTenant);
  }, []);

  const fetchCollections = useCallback(async () => {
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

      const response = await fetch(`${apiBase}/api/v1/collections?${params}`, {
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` })
        }
      });

      if (response.ok) {
        const data = await response.json();
        setCollections(Array.isArray(data) ? data : data.items || []);
        setTotalItems(data.total || data.length || 0);

        // Build chart data
        const chartAgg = { not_due: 0, due: 0, overdue_30: 0, overdue_60: 0, overdue_90: 0 };
        (Array.isArray(data) ? data : data.items || []).forEach((item: CollectionData) => {
          chartAgg[item.status] = (chartAgg[item.status] || 0) + item.outstanding_amount;
        });

        setChartData([
          { name: "Not Due", amount: chartAgg.not_due / 100000, color: "#10b981" },
          { name: "Due", amount: chartAgg.due / 100000, color: "#f59e0b" },
          { name: "Overdue 30d", amount: chartAgg.overdue_30 / 100000, color: "#ef4444" },
          { name: "Overdue 60d", amount: chartAgg.overdue_60 / 100000, color: "#dc2626" }
        ]);
      } else {
        setError("Failed to load collections");
      }
    } catch (err) {
      setError("Network error");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [tenantId, apiBase, token, currentPage, pageSize, searchQuery, filterStatus]);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "not_due":
        return "bg-emerald-100 text-emerald-700";
      case "due":
        return "bg-amber-100 text-amber-700";
      case "overdue_30":
        return "bg-orange-100 text-orange-700";
      case "overdue_60":
        return "bg-rose-100 text-rose-700";
      case "overdue_90":
        return "bg-red-100 text-red-700";
      default:
        return "bg-slate-100 text-slate-700";
    }
  };

  const totalPages = Math.ceil(totalItems / pageSize);

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Collections" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-800">Collections</h1>
                <p className="text-xs text-slate-400 font-semibold mt-1">Track aging receivables and manage collections</p>
              </div>
              <button className="flex items-center gap-2 px-4 py-2 bg-white border border-dashboard-border rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors">
                <Download className="w-4 h-4" />
                Export
              </button>
            </div>

            {/* Aging Analysis Chart */}
            {loading ? (
              <ChartSkeleton />
            ) : (
              <div className="bg-white rounded-lg border border-dashboard-border shadow-sm p-6">
                <h2 className="text-lg font-bold text-slate-800 mb-4">Aging Analysis (₹ in Lakhs)</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => `₹${value}L`} />
                    <Bar dataKey="amount" fill="#1e62ec" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Search & Filter */}
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by customer name..."
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
                <option value="not_due">Not Due</option>
                <option value="due">Due</option>
                <option value="overdue_30">Overdue 30d</option>
                <option value="overdue_60">Overdue 60d</option>
              </select>
            </div>

            {error && (
              <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-800">{error}</p>
                  <button onClick={fetchCollections} className="text-xs font-semibold text-rose-600 hover:text-rose-700 mt-1 underline">
                    Try again
                  </button>
                </div>
              </div>
            )}

            {/* Collections Table */}
            {loading ? (
              <TableSkeleton rows={5} />
            ) : collections.length === 0 ? (
              <EmptyState title="No receivables" description="All payments are collected" customIcon="collections" />
            ) : (
              <>
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="border-b border-dashboard-border bg-slate-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Customer</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Outstanding</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Days Overdue</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Status</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Last Payment</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dashboard-border">
                        {collections.map((item) => (
                          <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{item.customer_name}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">₹{item.outstanding_amount.toLocaleString("en-IN")}</p>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                {item.days_overdue > 0 && <TrendingDown className="w-4 h-4 text-rose-600" />}
                                <p className="text-sm font-semibold text-slate-800">{Math.max(0, item.days_overdue)} days</p>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${getStatusColor(item.status)}`}>
                                {item.status.replace(/_/g, " ")}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                                <p className="text-xs text-slate-500">{new Date(item.last_payment_date).toLocaleDateString()}</p>
                              </div>
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
