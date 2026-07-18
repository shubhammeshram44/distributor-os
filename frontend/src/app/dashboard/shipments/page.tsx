"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { formatDateTime } from "@/utils/datetime";
import { useDebounce, fetchWithTimeout } from "@/lib/debounce";
import {
  Loader2,
  AlertCircle,
  Truck,
  Users,
  Navigation,
  DollarSign,
  TrendingUp,
  X,
  CheckCircle2,
  ChevronDown
} from "lucide-react";


interface PendingOrder {
  order_id: string;
  internal_order_id: string;
  customer_name: string;
  invoice_amount: number;
}

interface ActiveShipment {
  shipment_id: string;
  driver_name: string;
  vehicle_number: string;
  status: string;
  order_id: string;
  internal_order_id: string;
  customer_name: string;
  invoice_amount: number;
  is_paid: boolean;
}

interface Driver {
  id: string;
  full_name: string;
  phone_number: string;
}


export default function ShipmentsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [activeShipments, setActiveShipments] = useState<ActiveShipment[]>([]);
  const [selectedOrderIds, setSelectedOrderIds] = useState<string[]>([]);
  
  // Search, Filter & Keyset Pagination states
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [pendingCursor, setPendingCursor] = useState<string | null>(null);
  const [activeCursor, setActiveCursor] = useState<string | null>(null);

  // Form states
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [selectedDriverId, setSelectedDriverId] = useState("");
  const [vehicleNumber, setVehicleNumber] = useState("");

  
  // Status states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRun, setSavingRun] = useState(false);
  const [markingDeliveredId, setMarkingDeliveredId] = useState<string | null>(null);

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

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

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

  // Fetch pending orders & active runs
  const fetchShipmentData = useCallback(async (isBackground = false) => {
    if (!isBackground) {
      setLoading(true);
    }
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      
      const pendingParams = new URLSearchParams();
      if (debouncedSearchQuery) pendingParams.append("q", debouncedSearchQuery);
      pendingParams.append("limit", "20");

      const activeParams = new URLSearchParams();
      if (debouncedSearchQuery) activeParams.append("q", debouncedSearchQuery);
      if (statusFilter) activeParams.append("status", statusFilter);
      activeParams.append("limit", "20");

      const [pendingResp, activeResp] = await Promise.all([
        fetchWithTimeout(`${apiBase}/api/v1/shipments/pending?${pendingParams.toString()}`, { credentials: "include", timeout: 12000 }),
        fetchWithTimeout(`${apiBase}/api/v1/shipments/active?${activeParams.toString()}`, { credentials: "include", timeout: 12000 })
      ]);

      if (!pendingResp.ok || !activeResp.ok) {
        throw new Error("Failed to load shipments metadata from database");
      }

      const pendingData = await pendingResp.json();
      const activeData = await activeResp.json();

      const newPending = pendingData.items || [];
      const newActive = activeData.items || [];

      // Diff state to prevent unnecessary re-renders
      setPendingOrders(prev => {
        if (JSON.stringify(prev) !== JSON.stringify(newPending)) {
          return newPending;
        }
        return prev;
      });

      setActiveShipments(prev => {
        if (JSON.stringify(prev) !== JSON.stringify(newActive)) {
          return newActive;
        }
        return prev;
      });

      setPendingCursor(pendingData.next_cursor || null);
      setActiveCursor(activeData.next_cursor || null);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load shipments");
    } finally {
      if (!isBackground) {
        setLoading(false);
      }
    }
  }, [debouncedSearchQuery, statusFilter]);

  const loadMorePending = async () => {
    if (!pendingCursor) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const params = new URLSearchParams();
      if (debouncedSearchQuery) params.append("q", debouncedSearchQuery);
      params.append("limit", "20");
      params.append("cursor", pendingCursor);

      const resp = await fetch(`${apiBase}/api/v1/shipments/pending?${params.toString()}`, { credentials: "include" });
      if (resp.ok) {
        const data = await resp.json();
        const newItems = data.items || [];
        setPendingOrders(prev => [...prev, ...newItems]);
        setPendingCursor(data.next_cursor || null);
      }
    } catch (err) {
      console.error("Failed to load more pending", err);
    }
  };

  const loadMoreActive = async () => {
    if (!activeCursor) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const params = new URLSearchParams();
      if (debouncedSearchQuery) params.append("q", debouncedSearchQuery);
      if (statusFilter) params.append("status", statusFilter);
      params.append("limit", "20");
      params.append("cursor", activeCursor);

      const resp = await fetch(`${apiBase}/api/v1/shipments/active?${params.toString()}`, { credentials: "include" });
      if (resp.ok) {
        const data = await resp.json();
        const newItems = data.items || [];
        setActiveShipments(prev => [...prev, ...newItems]);
        setActiveCursor(data.next_cursor || null);
      }
    } catch (err) {
      console.error("Failed to load more active", err);
    }
  };

  const fetchDrivers = useCallback(async (tenantId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/users?role=Driver&tenant_id=${tenantId}`, { credentials: "include" });
      if (resp.ok) {
        const data = await resp.json();
        setDrivers(data);
        if (data.length > 0) {
          setSelectedDriverId(data[0].id);
        } else {
          setSelectedDriverId("");
        }
      }
    } catch (err) {
      console.error("Failed to load drivers", err);
    }
  }, []);

  useEffect(() => {
    fetchShipmentData();
    if (activeTenantId) {
      fetchDrivers(activeTenantId);
    }
    setSelectedOrderIds([]);
  }, [activeTenantId, fetchShipmentData, fetchDrivers]);

  const isActionInProgress = selectedOrderIds.length > 0 || vehicleNumber.trim() !== "" || savingRun || markingDeliveredId !== null;

  // Tab focus revalidation and background sync to resolve cache lag
  useEffect(() => {
    const handleFocus = () => {
      if (document.visibilityState === "visible" && !isActionInProgress) {
        fetchShipmentData(true);
        if (activeTenantId) {
          fetchDrivers(activeTenantId);
        }
      }
    };
    window.addEventListener("focus", handleFocus);
    
    // Increased poll interval to 30s as a stopgap (should move to WebSocket/SSE push or ETag/304 polling later instead of fixed-interval polling)
    const interval = setInterval(handleFocus, 30000);

    return () => {
      window.removeEventListener("focus", handleFocus);
      clearInterval(interval);
    };
  }, [activeTenantId, fetchShipmentData, fetchDrivers, isActionInProgress]);


  // Create Delivery Run & Dispatch
  const handleCreateDeliveryRun = async (e: React.FormEvent) => {
    e.preventDefault();

    if (selectedOrderIds.length === 0) {
      showToast("Select at least one order checklist item to load.", "error");
      return;
    }
    if (!selectedDriverId || !vehicleNumber.trim()) {
      showToast("Driver selection and Vehicle Number are required.", "error");
      return;
    }

    setSavingRun(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(`${apiBase}/api/v1/shipments`, {
        method: "POST",
        credentials: "include",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          driver_id: selectedDriverId,
          vehicle_number: vehicleNumber.trim(),
          order_ids: selectedOrderIds
        })
      });

      const resData = await resp.json();
      if (resp.ok) {
        showToast(`Delivery Run created with ${selectedOrderIds.length} orders dispatched!`, "success");
        setVehicleNumber("");
        setSelectedOrderIds([]);
        setTimeout(() => fetchShipmentData(), 50);
      } else {
        showToast(resData.detail || "Failed to dispatch run.", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network break during dispatch creation.", "error");
    } finally {
      setSavingRun(false);
    }
  };


  // Mark Delivered
  const handleMarkDelivered = async (shipmentId: string) => {
    setMarkingDeliveredId(shipmentId);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(`${apiBase}/api/v1/shipments/${shipmentId}/status`, {
        method: "PATCH",
        credentials: "include",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          status: "Delivered",
          source: "back_office"
        })
      });

      const resData = await resp.json();
      if (resp.ok) {
        showToast("Shipment marked as Delivered successfully!", "success");
        setTimeout(() => fetchShipmentData(), 50);
      } else {
        showToast(resData.detail || "Failed to mark delivered.", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network break during status transition.", "error");
    } finally {
      setMarkingDeliveredId(null);
    }
  };

  const handleCheckboxToggle = (orderId: string) => {
    setSelectedOrderIds(prev =>
      prev.includes(orderId) ? prev.filter(id => id !== orderId) : [...prev, orderId]
    );
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  // Derived metrics
  const pendingAllocationCount = pendingOrders.length;
  const shipments = activeShipments;
  const hasNoShipments = !shipments || shipments.length === 0;
  const activeVehicles = shipments
    ? shipments.filter(s => s.status !== "Delivered").map(s => s.vehicle_number)
    : [];
  const activeDispatchedRunsCount = new Set(activeVehicles).size;

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-dashboard-inset">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800 dark:text-slate-100">
      <Sidebar
        activeTab="Shipments"
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
          {/* Header Banners */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight flex items-center gap-2">
                <Truck className="w-5 h-5 text-brand-blue" />
                <span>Shipments & Logistics Hub</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Dispatch verified invoices, compile delivery runs, track carrier milestones, and log handovers
              </p>
            </div>
          </div>

          {/* Quick Stats Banners */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Pending Vehicle Allocation</p>
                <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">{pendingAllocationCount}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Confirmed orders waiting dispatch</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-brand-blue shadow-sm">
                <Navigation className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Dispatched Runs</p>
                <h3 className="text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">{activeDispatchedRunsCount}</h3>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">Vehicles currently on route</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 shadow-sm">
                <Truck className="w-5 h-5" />
              </div>
            </div>
          </div>

          {loading && (
            <div className="flex flex-col items-center justify-center py-24 gap-3 bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border">
              <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
              <span className="text-sm font-semibold text-slate-500 dark:text-slate-500">Retrieving logistics status...</span>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600 bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border">
              <AlertCircle className="w-8 h-8" />
              <span className="text-sm font-semibold">{error}</span>
            </div>
          )}

          {!loading && !error && (
            <div className="space-y-6">
              {/* Search & Filter Bar */}
              <div className="bg-white dark:bg-dashboard-card p-4 rounded-xl border border-dashboard-border shadow-sm flex flex-col sm:flex-row gap-4 items-center justify-between">
                <div className="relative w-full sm:max-w-md">
                  <input
                    type="text"
                    placeholder="Search customer, order ID, or tracking ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-white/10 rounded-lg text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-brand-blue"
                  />
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full sm:w-48 p-2 border border-slate-200 dark:border-white/10 rounded-lg text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white dark:bg-dashboard-card cursor-pointer"
                  >
                    <option value="">All Milestone Statuses</option>
                    <option value="Created">Created</option>
                    <option value="Out For Delivery">Out For Delivery</option>
                    <option value="Delivered">Delivered</option>
                  </select>
                </div>
              </div>

              {/* Split-Screen Interactive Builder */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Tabular Checklist */}
                <div className="lg:col-span-2 bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm p-5 flex flex-col min-h-[350px]">
                  <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider">
                    Unallocated Orders Checklist
                  </h3>
                  <div className="flex-1 overflow-y-auto border border-slate-100 dark:border-white/5 rounded-lg mb-3">
                    {pendingOrders.length === 0 ? (
                      <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-200 dark:border-white/10 rounded-xl bg-slate-50/40 text-center my-4 mx-6">
                        <div className="p-3 bg-slate-100 dark:bg-white/5 text-slate-400 rounded-full mb-3">
                          <Truck className="w-6 h-6" />
                        </div>
                        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Your workspace is clean</h3>
                        <p className="text-xs text-slate-500 dark:text-slate-500 max-w-xs mt-1">
                          Connect your warehouse stock or send your first WhatsApp text order to see live tracking metrics update instantly.
                        </p>
                      </div>
                    ) : (
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="text-slate-400 font-bold border-b border-dashboard-border bg-slate-50 dark:bg-dashboard-inset">
                            <th className="py-2.5 px-4 text-center w-12">Load</th>
                            <th className="py-2.5 px-4">Order ID</th>
                            <th className="py-2.5 px-4">Store Name</th>
                            <th className="py-2.5 px-4 text-right">Invoice Amount</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-white/5 font-medium">
                          {pendingOrders.map(o => (
                            <tr key={o.order_id} className="hover:bg-slate-50/50">
                              <td className="py-3 px-4 text-center">
                                <input
                                  type="checkbox"
                                  checked={selectedOrderIds.includes(o.order_id)}
                                  onChange={() => handleCheckboxToggle(o.order_id)}
                                  className="w-3.5 h-3.5 rounded border-slate-300 dark:border-white/10 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                />
                              </td>
                              <td className="py-3 px-4 font-bold text-slate-700 dark:text-slate-300">{o.internal_order_id}</td>
                              <td className="py-3 px-4 text-slate-500 dark:text-slate-500">{o.customer_name}</td>
                              <td className="py-3 px-4 text-right font-bold text-slate-700 dark:text-slate-300">
                                {formatCurrency(o.invoice_amount)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                  {pendingCursor && (
                    <div className="flex justify-center border-t border-slate-100 dark:border-white/5 pt-3">
                      <button
                        onClick={loadMorePending}
                        className="px-4 py-1.5 bg-slate-50 dark:bg-dashboard-inset border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 text-[10px] font-bold rounded-lg transition-all cursor-pointer shadow-sm"
                      >
                        Load More Orders
                      </button>
                    </div>
                  )}
                </div>

                {/* Right: Input Terminal Card */}
                <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm p-5 flex flex-col justify-between min-h-[350px]">
                  <div>
                    <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider">
                      Dispatch Terminal
                    </h3>
                    <p className="text-[11px] text-slate-400 font-semibold mb-5 leading-relaxed">
                      Enter transport carrier credentials to allocate selected checklist items to a delivery run.
                    </p>
                  </div>

                  <form onSubmit={handleCreateDeliveryRun} className="space-y-4 flex-1 flex flex-col justify-between">
                    <div className="space-y-3">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 dark:text-slate-500 mb-1 uppercase">Driver Name</label>
                        <div className="relative">
                          <select
                            value={selectedDriverId}
                            onChange={(e) => setSelectedDriverId(e.target.value)}
                            className="w-full p-2.5 pr-8 border border-slate-200 dark:border-white/10 rounded-lg text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer bg-white dark:bg-dashboard-card appearance-none text-slate-700 dark:text-slate-300"
                            required
                          >
                            <option value="" disabled>Select Driver...</option>
                            {drivers.map((drv) => (
                              <option key={drv.id} value={drv.id}>
                                {drv.full_name} ({drv.phone_number})
                              </option>
                            ))}
                          </select>
                          <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                        </div>
                      </div>

                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 dark:text-slate-500 mb-1 uppercase">Vehicle Number</label>
                        <input
                          type="text"
                          value={vehicleNumber}
                          onChange={(e) => setVehicleNumber(e.target.value)}
                          placeholder="e.g. KA-01-MJ-9876"
                          className="w-full p-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-brand-blue"
                          required
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={savingRun || selectedOrderIds.length === 0}
                      className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
                    >
                      {savingRun ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Dispatching...</span>
                        </>
                      ) : (
                        <span>Create Delivery Run & Dispatch ({selectedOrderIds.length})</span>
                      )}
                    </button>
                  </form>
                </div>
              </div>

              {/* Active Fulfillment Ledger */}
              <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[300px]">
                <div className="p-4 border-b border-dashboard-border bg-slate-50 dark:bg-dashboard-inset rounded-t-xl">
                  <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Active Shipments Ledger
                  </h3>
                </div>

                {hasNoShipments ? (
                  <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-200 dark:border-white/10 rounded-xl bg-slate-50/40 text-center my-4 mx-6">
                    <div className="p-3 bg-slate-100 dark:bg-white/5 text-slate-400 rounded-full mb-3">
                      <Truck className="w-6 h-6" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Your workspace is clean</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-500 max-w-xs mt-1">
                      Connect your warehouse stock or send your first WhatsApp text order to see live tracking metrics update instantly.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="text-slate-400 font-bold border-b border-dashboard-border bg-slate-50/50">
                          <th className="py-3 px-6">Shipment Context</th>
                          <th className="py-3 px-6">Driver & Vehicle</th>
                          <th className="py-3 px-6">Commercial Link</th>
                          <th className="py-3 px-6">Milestone Status</th>
                          <th className="py-3 px-6">Payment status</th>
                          <th className="py-3 px-6 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-white/5 font-semibold text-slate-700 dark:text-slate-300">
                        {shipments.map(s => (
                          <tr key={s.shipment_id} className="hover:bg-slate-50/50 transition-colors">
                            <td className="py-4 px-6">
                              <span className="font-bold text-slate-800 dark:text-slate-100">{s.shipment_id.slice(0, 8).toUpperCase()}...</span>
                            </td>
                            <td className="py-4 px-6 text-slate-600 dark:text-slate-400">
                              <div>{s.driver_name}</div>
                              <div className="text-[10px] text-slate-400 mt-0.5">{s.vehicle_number}</div>
                            </td>
                            <td className="py-4 px-6">
                              <div>{s.internal_order_id}</div>
                              <div className="text-[10px] text-slate-400 mt-0.5">{s.customer_name}</div>
                            </td>
                            <td className="py-4 px-6">
                              <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                s.status === "Delivered"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-amber-50 text-amber-700 border-amber-200"
                              }`}>
                                {s.status}
                              </span>
                            </td>
                            <td className="py-4 px-6">
                              {s.is_paid ? (
                                <span className="text-emerald-600 font-bold flex items-center gap-1">
                                  <span>🟢 Paid</span>
                                </span>
                              ) : (
                                <span className="text-rose-600 font-bold flex items-center gap-1">
                                  <span>🔴 Unpaid (Credit Account)</span>
                                </span>
                              )}
                            </td>
                            <td className="py-4 px-6 text-center">
                              {s.status !== "Delivered" ? (
                                <button
                                  onClick={() => handleMarkDelivered(s.shipment_id)}
                                  disabled={markingDeliveredId === s.shipment_id}
                                  className="px-3 py-1.5 bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 text-[10px] font-bold rounded-lg transition-all cursor-pointer inline-flex items-center gap-1"
                                >
                                  {markingDeliveredId === s.shipment_id ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <span>Mark Delivered</span>
                                  )}
                                </button>
                              ) : (
                                <span className="text-slate-400 text-[10px] font-bold flex items-center justify-center gap-1">
                                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                  <span>Completed</span>
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {activeCursor && (
                  <div className="flex justify-center border-t border-slate-100 dark:border-white/5 p-4">
                    <button
                      onClick={loadMoreActive}
                      className="px-4 py-1.5 bg-slate-50 dark:bg-dashboard-inset border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 text-[10px] font-bold rounded-lg transition-all cursor-pointer shadow-sm"
                    >
                      Load More Shipments
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Sleek Floating Toast Notification */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 dark:bg-dashboard-card/95 backdrop-blur-md border border-slate-100 dark:border-white/5 shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-w-sm">
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
            <p className="text-xs font-bold text-slate-800 dark:text-slate-100">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-500 font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 dark:hover:bg-white/5 transition-all shrink-0 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
