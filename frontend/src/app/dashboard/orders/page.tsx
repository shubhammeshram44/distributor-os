"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { InvoiceTypes, InvoiceType } from "@/types/order";
import Pagination from "@/components/ui/Pagination";
import { formatDateTime } from "@/utils/datetime";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/ui/Toast";
import PlaceOrderModal from "@/components/PlaceOrderModal";
import { useDebounce, fetchWithTimeout } from "@/lib/debounce";
import {
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  X,
  MessageSquare,
  Globe,
  FileSpreadsheet,
  ChevronRight,
  Download,
  SlidersHorizontal,
  ChevronDown,
  ShoppingCart
} from "lucide-react";

interface OrderItem {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
  allocated_quantity: number | null;
  unit_price: number;
  total_price: number;
  raw_source_text?: string;
  product_id?: string | null;
  isResolvedLocally?: boolean;
  resolvedSkuCode?: string;
}

interface OrderRow {
  id: string;
  order_id: string;
  customer: string;
  channel: string;
  amount: number;
  status: string;
  created_on: string;
  eta: string;
  payment_status: string;
  amount_paid: number;
  invoice_type: InvoiceType;
  raw_source_text?: string;
  line_items?: any[];
}

export default function OrdersPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [selectedStatus, setSelectedStatus] = useState<"All" | "Pending" | "Confirmed" | "Needs Review">("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditingInvoiceType, setIsEditingInvoiceType] = useState(false);
  const [riskAssessment, setRiskAssessment] = useState<any>(null);
  const [riskLoading, setRiskLoading] = useState(false);

  // Bulk Job States
  const [bulkJobId, setBulkJobId] = useState<string | null>(null);
  const [bulkProgress, setBulkProgress] = useState<number>(0);
  const [bulkStatus, setBulkStatus] = useState<"PENDING" | "PROCESSING" | "COMPLETED" | "PARTIALLY_COMPLETED" | "FAILED" | null>(null);
  const [bulkResultLink, setBulkResultLink] = useState<string | null>(null);
  const [bulkFailedOrders, setBulkFailedOrders] = useState<{ order_id: string; error: string }[] | null>(null);
  const [isBulkProcessing, setIsBulkProcessing] = useState<boolean>(false);

  // Drawer States
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [selectedOrderNo, setSelectedOrderNo] = useState<string>("");
  const [selectedOrderDetails, setSelectedOrderDetails] = useState<OrderItem[] | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isMarkingDelivered, setIsMarkingDelivered] = useState(false);
  const [productsList, setProductsList] = useState<any[]>([]);
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null);
  const [editedLineItems, setEditedLineItems] = useState<any[]>([]);
  const [selectedOrderPayments, setSelectedOrderPayments] = useState<{
    payment_status: string;
    payments_allocated: {
      payment_code: string;
      amount_allocated: number;
      total_voucher_amount: number;
      method: string;
      reference_number: string | null;
      created_at: string;
    }[];
    invoice_id?: string | null;
  } | null>(null);

  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 50;
  const [isCancelDialogOpen, setIsCancelDialogOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isPlaceOrderOpen, setIsPlaceOrderOpen] = useState(false);

  const { toasts, toast: toastQueue, removeToast } = useToast();

  const foundOrder = orders.find(o => o.id === selectedOrderId);
  const selectedOrder = foundOrder
    ? {
      ...foundOrder,
      line_items: selectedOrderDetails || undefined
    }
    : null;

  useEffect(() => {
    if (selectedOrder && selectedOrder.line_items && selectedOrder.line_items.length > 0) {
      setEditedLineItems(prev => {
        const firstPrevId = prev[0]?.id;
        const firstNewId = selectedOrder.line_items![0]?.id;
        if (firstPrevId !== firstNewId) {
          return selectedOrder.line_items!;
        }
        return prev;
      });
    }
  }, [selectedOrder]);

  const showToast = (message: string, type: "success" | "error") => {
    toastQueue[type](message);
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

  // Fetch all orders for active tenant
  const fetchOrders = useCallback(async (tenantId?: string, newSkip?: number) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    const currentSkip = newSkip !== undefined ? newSkip : skip;
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetchWithTimeout(
        `${apiBase}/api/v1/orders?tenant_id=${targetTenant}&skip=${currentSkip}&limit=${limit}`,
        { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {}, timeout: 12000 }
      );
      if (!resp.ok) throw new Error("Failed to fetch orders");
      const data = await resp.json();
      setOrders(data.items ?? data);
      setTotal(data.total ?? (data.items ?? data).length);
      setError(null);
    } catch (err: any) {
      console.error("Orders load failed:", err);
      setError(err.message || "Failed to load orders from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId, skip, limit]);


  // Fetch products for resolving dropdowns
  useEffect(() => {
    const fetchProducts = async () => {
      if (!activeTenantId) return;
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}&limit=200`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setProductsList(data.items ?? data);
        }
      } catch (err) {
        console.error("Failed to load products list for resolution drawer:", err);
      }
    };
    fetchProducts();
  }, [activeTenantId]);

  useEffect(() => {
    if (!activeTenantId) return;
    setOrders([]);
    setSkip(0);
    fetchOrders(activeTenantId, 0);
  }, [activeTenantId]);

  const handlePageChange = (newSkip: number) => {
    setSkip(newSkip);
    fetchOrders(activeTenantId, newSkip);
  };

  const handleCancelOrder = async () => {
    if (!selectedOrderId) return;
    setIsCancelling(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/cancel`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }
      });
      if (!resp.ok) {
        const d = await resp.json();
        throw new Error(d.detail || "Failed to cancel order");
      }
      showToast("Order cancelled successfully.", "success");
      setIsCancelDialogOpen(false);
      handleCloseDetails();
      fetchOrders(activeTenantId, skip);
    } catch (err: any) {
      showToast(err.message || "Failed to cancel order.", "error");
    } finally {
      setIsCancelling(false);
    }
  };

  const handleExportCSV = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const url = `${apiBase}/api/v1/orders/export?tenant_id=${activeTenantId}`;
    // Open in new tab to trigger file download
    window.open(url, "_blank");
  };

  // Tally export — lets distributors keep using Tally for their CA/GST
  // filing while DistributorOS handles WhatsApp order capture, instead of
  // manually re-typing every confirmed order into Tally.
  const [showTallyExportModal, setShowTallyExportModal] = useState(false);
  const [tallyExportError, setTallyExportError] = useState<string | null>(null);
  const [tallyStartDate, setTallyStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [tallyEndDate, setTallyEndDate] = useState(() => new Date().toISOString().split("T")[0]);

  const handleExportTally = async () => {
    setTallyExportError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const params = new URLSearchParams({
      tenant_id: activeTenantId,
      start_date: tallyStartDate,
      end_date: tallyEndDate,
    });
    try {
      const resp = await fetch(`${apiBase}/api/v1/orders/export/tally?${params.toString()}`, {
        credentials: "include",
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "No confirmed orders found in the selected date range.");
      }
      const blob = await resp.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `tally_export_${tallyStartDate}_to_${tallyEndDate}.xml`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      setShowTallyExportModal(false);
      showToast("Tally export downloaded. Import it via Gateway of Tally \u2192 Import Data \u2192 Vouchers.", "success");
    } catch (err: any) {
      setTallyExportError(err.message || "Failed to export to Tally.");
    }
  };


  useEffect(() => {
    if (!selectedOrderId) {
      setRiskAssessment(null);
      return;
    }
    const orderToAssess = orders.find(o => o.id === selectedOrderId);
    if (!orderToAssess) return;

    const status = orderToAssess.status;
    const isPendingOrDraft = status === "Pending" || status === "Draft" || status === "Needs Review";

    if (isPendingOrDraft) {
      const fetchRiskAssessment = async () => {
        setRiskLoading(true);
        try {
          const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
          const resp = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/risk-assessment`, {
            credentials: "include"
          });
          if (resp.ok) {
            const data = await resp.json();
            setRiskAssessment(data);
          } else {
            setRiskAssessment(null);
          }
        } catch (err) {
          console.error(err);
          setRiskAssessment(null);
        } finally {
          setRiskLoading(false);
        }
      };
      fetchRiskAssessment();
    } else {
      setRiskAssessment(null);
    }
  }, [selectedOrderId, orders]);


  const fetchOrderDetails = async (orderId: string) => {
    setLoadingDetails(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/dashboard/order-details/${orderId}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to load order line item details");
      const data = await resp.json();
      setSelectedOrderDetails(data);

      const orderResp = await fetch(`${apiBase}/api/v1/orders/${orderId}`, {
        credentials: "include"
      });
      if (orderResp.ok) {
        const orderData = await orderResp.json();
        setSelectedOrderPayments(orderData);
      } else {
        setSelectedOrderPayments(null);
      }
    } catch (err: any) {
      console.error(err);
      showToast("Failed to load order details.", "error");
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleOrderIdClick = async (order: OrderRow) => {
    setIsEditingInvoiceType(false);
    setSelectedOrderId(order.id);
    setSelectedOrderNo(order.order_id);
    await fetchOrderDetails(order.id);
  };

  const handleCloseDetails = () => {
    setIsEditingInvoiceType(false);
    setSelectedOrderId(null);
    setSelectedOrderDetails(null);
    setSelectedOrderPayments(null);
  };

  const handleConfirmOrder = async () => {
    if (!selectedOrderId) return;
    setIsConfirming(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

      // Collect all locally-staged resolutions into the batch payload matching backend schema
      const resolved_items = editedLineItems
        .filter(item => item.product_id !== null && item.product_id !== undefined)
        .map(item => ({
          item_id: item.id,
          product_id: item.product_id,
        }));

      // Single atomic request: resolve staged items + confirm + self-learning in one shot
      const response = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/batch-confirm`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          invoice_type: selectedOrder?.invoice_type || "UNSPECIFIED",
          resolved_items,
        }),
      });
      const data = await response.json();
      if (response.ok) {
        showToast("Order confirmed successfully!", "success");
        await fetchOrders(activeTenantId);
        await fetchOrderDetails(selectedOrderId);
      } else {
        const errorDetail = data.detail || "Failed to confirm order.";
        showToast(errorDetail, "error");
      }
    } catch (err: any) {
      showToast(err.message || "Network connection breakdown during order confirmation.", "error");
    } finally {
      setIsConfirming(false);
    }
  };

  const handleMarkDelivered = async () => {
    if (!selectedOrderId) return;
    setIsMarkingDelivered(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/${selectedOrderId}/delivery-event`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "delivered",
          source: "manual",
          tenant_id: activeTenantId
        })
      });
      const data = await response.json();
      if (response.ok) {
        showToast("Order marked as delivered. Customer notified.", "success");
        handleCloseDetails();
        fetchOrders(activeTenantId);
      } else {
        const errorDetail = data.detail || "Failed to mark order as delivered.";
        showToast(errorDetail, "error");
      }
    } catch (err: any) {
      showToast(err.message || "Network connection error while marking order as delivered.", "error");
    } finally {
      setIsMarkingDelivered(false);
    }
  };

  const handleProductChange = (itemId: string, selectedProductId: string) => {
    const targetProduct = productsList.find(p => p.id === selectedProductId);
    setEditedLineItems((prevItems) =>
      prevItems.map((item) =>
        item.id === itemId
          ? {
            ...item,
            product_id: selectedProductId,
            unmatched_raw_text: null,
            sku_id: targetProduct ? targetProduct.sku_id : item.sku_id,
            brand: targetProduct ? targetProduct.brand : item.brand,
            category: targetProduct ? targetProduct.category : item.category,
            pack_size: targetProduct ? targetProduct.pack_size : item.pack_size,
            unit_price: targetProduct ? targetProduct.base_price : item.unit_price,
            total_price: targetProduct ? item.quantity * targetProduct.base_price : item.total_price,
            isResolvedLocally: true,
            resolvedSkuCode: targetProduct ? targetProduct.sku_id : undefined,
          }
          : item
      )
    );
  };

  const handleUpdateInvoiceType = async (orderId: string, newType: InvoiceType) => {
    const previousOrderState = [...orders];

    setOrders(prevOrders =>
      prevOrders.map(o => (o.id === orderId ? { ...o, invoice_type: newType } : o))
    );

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/${orderId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invoice_type: newType })
      });

      if (!response.ok) {
        throw new Error("Failed to update invoice type.");
      }
      showToast("Invoice type updated successfully!", "success");
    } catch (err: any) {
      console.error("Failed to update invoice type:", err);
      setOrders(previousOrderState);
      showToast(err.message || "Failed to update invoice type.", "error");
    } finally {
      setIsEditingInvoiceType(false);
    }
  };

  const renderInvoiceTypeBadge = (type: InvoiceType) => {
    switch (type) {
      case InvoiceTypes.GST:
        return (
          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none bg-purple-50 text-purple-700 border border-purple-200 shadow-sm">
            GST Bill
          </span>
        );
      case InvoiceTypes.RETAIL:
        return (
          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none bg-blue-50 text-blue-700 border border-blue-200 shadow-sm">
            Retail Bill
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none bg-slate-50 text-slate-500 border border-slate-200 shadow-sm">
            Unspecified
          </span>
        );
    }
  };

  // Poll bulk action progress status
  useEffect(() => {
    if (!bulkJobId) return;

    const interval = setInterval(async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${apiBase}/api/v1/orders/bulk-action/${bulkJobId}`, {
          credentials: "include"
        });
        if (!res.ok) throw new Error("Failed to fetch job status");

        const data = await res.json();
        setBulkProgress(data.progress);
        setBulkStatus(data.status);
        setBulkResultLink(data.result_link);
        setBulkFailedOrders(data.failed_orders);

        if (data.status === "COMPLETED" || data.status === "PARTIALLY_COMPLETED" || data.status === "FAILED") {
          clearInterval(interval);
          setIsBulkProcessing(false);
          if (data.status === "COMPLETED") {
            showToast("Bulk invoice generation completed successfully!", "success");
          } else if (data.status === "PARTIALLY_COMPLETED") {
            showToast("Bulk invoice generation finished with some errors.", "error");
          } else {
            showToast("Bulk invoice generation failed completely.", "error");
          }
        }
      } catch (err) {
        console.error("Error polling bulk job status:", err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [bulkJobId]);

  const handleBulkDownloadInvoices = async () => {
    const confirmedOrders = orders.filter(o => o.status === "Confirmed");
    if (confirmedOrders.length === 0) {
      showToast("No confirmed orders found in this workspace.", "error");
      return;
    }

    setIsBulkProcessing(true);
    setBulkProgress(0);
    setBulkStatus("PENDING");
    setBulkResultLink(null);
    setBulkFailedOrders(null);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/orders/bulk-action`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_ids: confirmedOrders.map(o => o.id)
        })
      });

      if (!response.ok) {
        throw new Error("Failed to trigger bulk action.");
      }

      const data = await response.json();
      setBulkJobId(data.job_id);
    } catch (err: any) {
      console.error(err);
      showToast(err.message || "Failed to trigger bulk generation.", "error");
      setIsBulkProcessing(false);
      setBulkStatus(null);
    }
  };


  // Status Filter Counts
  const countAll = orders.length;
  const countPending = orders.filter(o => o.status === "Pending").length;
  const countConfirmed = orders.filter(o => o.status === "Confirmed").length;
  const countNeedsReview = orders.filter(o => o.status === "Needs Review").length;

  // Filter and Search Logic
  const filteredOrders = orders.filter(o => {
    const matchesStatus = selectedStatus === "All" || o.status === selectedStatus;
    const matchesSearch =
      o.order_id.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
      o.customer.toLowerCase().includes(debouncedSearchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
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
      <Sidebar
        activeTab="Orders"
        setActiveTab={() => { }}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          {/* Header Controls */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight">Order Management</h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Monitor and process orders from all sales channels (WhatsApp, B2B Portal)
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-slate-400" />
                <span>Export CSV</span>
              </button>

              <button
                onClick={() => setShowTallyExportModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
                title="Export confirmed orders as a Tally-importable XML"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
                <span>Export to Tally</span>
              </button>

              <button
                disabled={orders.filter(o => o.status === "Confirmed").length === 0 || isBulkProcessing}
                onClick={handleBulkDownloadInvoices}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-brand-blue text-white rounded-lg text-xs font-bold hover:bg-brand-blueHover disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed transition-all shadow-sm cursor-pointer animate-fade-in"
              >
                {isBulkProcessing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>Download Invoices</span>
                )}
              </button>

              <button
                onClick={() => setIsPlaceOrderOpen(true)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg flex items-center gap-2 transition-all cursor-pointer shadow-sm"
              >
                <ShoppingCart className="w-4 h-4" />
                + New Order
              </button>

              <button
                onClick={() => {
                  if (activeTenantId) {
                    fetchOrders(activeTenantId);
                  }
                }}
                className="flex items-center gap-1.5 px-3 py-2 border border-dashboard-border bg-white rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all shadow-sm cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                <span>Refresh Orders</span>
              </button>
            </div>

          </div>

          {/* Status Navigation & Search Bar Card */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Tab Filters */}
            <div className="flex flex-wrap items-center gap-1 bg-slate-100/80 p-1 rounded-xl">
              <button
                onClick={() => setSelectedStatus("All")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${selectedStatus === "All"
                  ? "bg-white text-brand-blue shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
                  }`}
              >
                <span>All</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "All" ? "bg-blue-50 text-brand-blue" : "bg-slate-200 text-slate-600"}`}>
                  {countAll}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Pending")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${selectedStatus === "Pending"
                  ? "bg-white text-brand-blue shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
                  }`}
              >
                <span>Pending</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Pending" ? "bg-amber-50 text-amber-700" : "bg-slate-200 text-slate-600"}`}>
                  {countPending}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Confirmed")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${selectedStatus === "Confirmed"
                  ? "bg-white text-brand-blue shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
                  }`}
              >
                <span>Confirmed</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Confirmed" ? "bg-emerald-50 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>
                  {countConfirmed}
                </span>
              </button>

              <button
                onClick={() => setSelectedStatus("Needs Review")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${selectedStatus === "Needs Review"
                  ? "bg-white text-brand-blue shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
                  }`}
              >
                <span>Needs Review</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${selectedStatus === "Needs Review" ? "bg-rose-50 text-rose-700" : "bg-slate-200 text-slate-600"}`}>
                  {countNeedsReview}
                </span>
              </button>
            </div>

            {/* Search input */}
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search order ID or retailer..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue text-slate-700 font-semibold"
              />
            </div>
          </div>

          {/* Master Orders Data Grid */}
          <div className="bg-white rounded-xl border border-dashboard-border shadow-sm overflow-hidden flex flex-col min-h-[400px]">
            <div className="flex-1 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3">
                  <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                  <span className="text-sm font-semibold text-slate-500">Loading orders catalog...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                  <AlertCircle className="w-8 h-8" />
                  <span className="text-sm font-semibold">{error}</span>
                  <button
                    onClick={() => {
                      if (activeTenantId) {
                        fetchOrders(activeTenantId);
                      }
                    }}
                    className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Try Again
                  </button>

                </div>
              ) : filteredOrders.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/40 text-center my-4">
                  <div className="p-3 bg-slate-100 text-slate-400 rounded-full mb-3">
                    <Search className="w-6 h-6" />
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
                      <th className="py-3 px-6">Order ID</th>
                      <th className="py-3 px-6">Customer</th>
                      <th className="py-3 px-6 text-center">Channel</th>
                      <th className="py-3 px-6 text-right">Amount</th>
                      <th className="py-3 px-6 text-center">Status</th>
                      <th className="py-3 px-6 text-center">PAYMENT</th>
                      <th className="py-3 px-6 text-center">Invoice Type</th>
                      <th className="py-3 px-6">Created On</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredOrders.map((order) => (
                      <tr key={order.id} className="hover:bg-slate-50/70 transition-colors group">
                        <td className="py-4 px-6 font-bold text-brand-blue hover:underline">
                          <button
                            onClick={() => handleOrderIdClick(order)}
                            className="cursor-pointer font-bold text-left focus:outline-none"
                          >
                            {order.order_id}
                          </button>
                        </td>
                        <td className="py-4 px-6 font-semibold text-slate-700">
                          {order.customer}
                        </td>
                        <td className="py-4 px-6 text-center">
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
                        <td className="py-4 px-6 text-right font-extrabold text-slate-800">
                          {formatCurrency(order.amount)}
                        </td>
                        <td className="py-4 px-6 text-center">
                          {(() => {
                            const totalRequested = order.line_items?.reduce((sum: number, i: any) => sum + i.quantity, 0) || 0;
                            const totalAllocated = order.line_items?.reduce((sum: number, i: any) => sum + (i.allocated_quantity !== null && i.allocated_quantity !== undefined ? i.allocated_quantity : i.quantity), 0) || 0;
                            const hasShortfall = totalAllocated < totalRequested;
                            if (order.status === "Confirmed" && hasShortfall) {
                              return (
                                <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none bg-amber-50 text-amber-700 border border-amber-200">
                                  Confirmed ({totalAllocated} of {totalRequested} allocated)
                                </span>
                              );
                            }
                            return (
                              <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-bold leading-none ${order.status === "Confirmed"
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : order.status === "Needs Review"
                                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                                    : "bg-amber-50 text-amber-700 border border-amber-200"
                                }`}>
                                {order.status}
                              </span>
                            );
                          })()}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`inline-flex items-center justify-center w-24 px-2.5 py-1 rounded-full text-xs font-bold leading-none ${order.payment_status === "PAID"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                            : order.payment_status === "PARTIALLY_PAID"
                              ? "bg-amber-50 text-amber-700 border border-amber-200/60"
                              : "bg-rose-50 text-rose-700 border border-rose-200/60"
                            }`}>
                            {order.payment_status === "PAID"
                              ? "🟢 Paid"
                              : order.payment_status === "PARTIALLY_PAID"
                                ? "🟡 Partial"
                                : "🔴 Unpaid"}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-center">
                          {renderInvoiceTypeBadge(order.invoice_type)}
                        </td>
                        <td className="py-4 px-6 text-xs font-semibold text-slate-500">
                          {formatDateTime(order.created_on, "datetime")}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <button
                            onClick={() => handleOrderIdClick(order)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-brand-blue hover:text-brand-blueHover cursor-pointer"
                          >
                            <span>Details</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Pagination */}
          {!loading && !error && total > limit && (
            <Pagination total={total} skip={skip} limit={limit} onPageChange={handlePageChange} />
          )}
        </main>
      </div>

      {/* Details Side Panel Drawer */}
      {selectedOrderId && (
        <div className="fixed inset-y-0 right-0 z-50 flex justify-end pointer-events-none">
          <div className="flex-1 pointer-events-none"></div>

          <div className="w-[500px] bg-white h-screen shadow-2xl flex flex-col animate-slide-in relative border-l border-slate-200 pointer-events-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-dashboard-border flex items-center justify-between bg-brand-dark text-white">
              <div>
                <h3 className="font-bold text-lg">Order Details</h3>
                <p className="text-xs text-brand-textMuted mt-0.5">ID: {selectedOrderNo}</p>
              </div>
              <button
                onClick={handleCloseDetails}
                className="p-1.5 rounded-full hover:bg-brand-darkHover text-brand-textMuted hover:text-white transition-all cursor-pointer"
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
              ) : editedLineItems && editedLineItems.length > 0 ? (
                <>
                  {/* Order Overview / Settings */}
                  <div className="bg-slate-50/50 border border-dashboard-border rounded-xl p-4 mb-4 space-y-3 relative z-30">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Retailer</span>
                      <span className="text-sm font-bold text-slate-700">{selectedOrder?.customer}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Channel</span>
                      <span className="text-xs font-bold text-slate-700 capitalize">{selectedOrder?.channel}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-semibold">Invoice Type</span>
                      <div className="flex items-center gap-2">
                        {isEditingInvoiceType ? (
                          <select
                            value={selectedOrder?.invoice_type || InvoiceTypes.UNSPECIFIED}
                            onChange={(e) => {
                              if (selectedOrderId) {
                                handleUpdateInvoiceType(selectedOrderId, e.target.value as InvoiceType);
                              }
                            }}
                            className="p-1 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 font-bold focus:outline-none focus:ring-2 focus:ring-brand-blue cursor-pointer z-40 relative shadow-sm"
                          >
                            <option value={InvoiceTypes.GST}>GST Tax Invoice</option>
                            <option value={InvoiceTypes.RETAIL}>Retail Tax Invoice</option>
                            <option value={InvoiceTypes.UNSPECIFIED}>Unspecified</option>
                          </select>
                        ) : (
                          <div className="flex items-center gap-1">
                            {renderInvoiceTypeBadge(selectedOrder?.invoice_type || InvoiceTypes.UNSPECIFIED)}
                            <button
                              onClick={() => setIsEditingInvoiceType(true)}
                              className="text-[10px] font-bold text-brand-blue hover:text-brand-blueHover cursor-pointer underline decoration-dotted"
                            >
                              Edit
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {selectedOrder?.raw_source_text && (
                    <div className="bg-gray-50 border border-gray-100 rounded-lg p-3 text-sm text-gray-700 italic my-3 flex items-start gap-2">
                      <MessageSquare className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                      <div>
                        <span className="font-bold text-xs text-slate-500 uppercase not-italic block mb-0.5">Original Message:</span>
                        "{selectedOrder.raw_source_text}"
                      </div>
                    </div>
                  )}

                  <h4 className="font-bold text-slate-800 text-sm border-b pb-2 mb-3">Line Items</h4>
                  {editedLineItems.map((item, idx) => {
                    const isUnmatched = item.sku_id === "UNMATCHED_SKU" || item.sku_id === "UNMATCHED_TRIAGE_SKU";
                    // Line total = allocated_quantity * unit_price (not full quantity)
                    const displayQty = item.allocated_quantity ?? item.quantity;
                    const lineTotal = displayQty * item.unit_price;
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
                                  value={item.product_id || ""}
                                  onChange={(e) => handleProductChange(item.id, e.target.value)}
                                  className="w-full mt-1 p-2 border border-rose-200 rounded-lg text-xs bg-white text-slate-700 font-semibold focus:outline-none focus:ring-1 focus:ring-rose-500 cursor-pointer animate-pulse"
                                >
                                  <option value="">-- Select SKU --</option>
                                  {productsList.map((p) => (
                                    <option key={p.id} value={p.id}>
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
                          <div className="flex flex-col items-end shrink-0 text-right text-xs font-bold text-slate-500">
                            {/* Show allocated quantity if partial, otherwise show full quantity */}
                            {item.allocated_quantity !== null && item.allocated_quantity !== undefined && item.allocated_quantity < item.quantity ? (
                              <span>
                                <span className="line-through text-gray-400">{item.quantity}</span>
                                {" "}{item.allocated_quantity} allocated
                              </span>
                            ) : (
                              <span>{item.allocated_quantity ?? item.quantity}</span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-2 mt-1">
                          <span className="text-xs text-slate-400">Rate: {formatCurrency(item.unit_price)}</span>
                          <span className="text-sm font-bold text-slate-800">{formatCurrency(lineTotal)}</span>
                        </div>
                      </div>
                    );
                  })}

                  {/* Financial Summary */}
                  <div className="border-t border-slate-200 pt-4 mt-6 space-y-2 text-sm">
                    <div className="flex justify-between text-slate-500 font-medium">
                      <span>Subtotal</span>
                      <span>{formatCurrency(editedLineItems.reduce((a, b) => a + b.total_price, 0) / 1.18)}</span>
                    </div>
                    <div className="flex justify-between text-slate-500 font-medium">
                      <span>GST (18%)</span>
                      <span>{formatCurrency(editedLineItems.reduce((a, b) => a + b.total_price, 0) * 0.18 / 1.18)}</span>
                    </div>
                    <div className="flex justify-between text-base font-extrabold text-slate-800 pt-2 border-t border-dashed">
                      <span>Total Amount</span>
                      <span>{formatCurrency(editedLineItems.reduce((a, b) => a + b.total_price, 0))}</span>
                    </div>
                  </div>

                  {/* Payment Receipt Audit Trail Box */}
                  {selectedOrderPayments && (selectedOrderPayments.payments_allocated.length > 0 || selectedOrderPayments.payment_status === "UNPAID") && (
                    <div className="border border-slate-200/80 rounded-lg p-4 mt-4 bg-slate-50/50">
                      <h5 className="font-bold text-slate-800 text-xs uppercase tracking-wider mb-3 flex items-center gap-1.5">
                        <span>💳 Payment Audit Trail</span>
                      </h5>

                      {selectedOrderPayments.payments_allocated.length > 0 ? (
                        <div className="space-y-3">
                          {selectedOrderPayments.payments_allocated.map((payment, idx) => (
                            <div key={idx} className="flex flex-col border-b border-dashed border-slate-200 pb-2 last:border-0 last:pb-0">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-bold font-mono text-slate-600">
                                  {payment.payment_code}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-xs text-slate-600 mt-1">
                                <span>Total Voucher Amount:</span>
                                <span className="font-semibold text-slate-700">₹{payment.total_voucher_amount.toLocaleString()}</span>
                              </div>
                              <div className="flex items-center justify-between text-xs text-slate-600 mt-1">
                                <span>Amount Applied to this Order:</span>
                                <span className="font-extrabold text-emerald-700">{formatCurrency(payment.amount_allocated)}</span>
                              </div>
                              <div className="flex items-center justify-between text-xs text-slate-600 mt-1">
                                <span>Method: <strong className="font-semibold text-slate-700">{payment.method}</strong></span>
                                <span>{new Date(payment.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                              </div>
                              {payment.reference_number && (
                                <div className="text-xs text-slate-600 mt-1 font-mono truncate">
                                  Ref: {payment.reference_number}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-rose-700 font-medium flex items-center gap-1.5">
                          <span>❌ No payments recorded yet against this invoice.</span>
                        </p>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-slate-400 py-12">No details available.</div>
              )}
            </div>

            {/* Footer Buttons */}
            <div className="p-6 border-t border-dashboard-border bg-slate-50 flex flex-col gap-3">
              {riskAssessment && selectedOrder?.status !== "Confirmed" && (
                <div className={`rounded-lg p-4 mb-4 border ${riskAssessment.level === "high_risk"
                    ? "bg-red-50 border-red-200"
                    : riskAssessment.level === "caution"
                      ? "bg-yellow-50 border-yellow-200"
                      : "bg-green-50 border-green-200"
                  }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">
                      {riskAssessment.level === "high_risk" ? "🔴" : riskAssessment.level === "caution" ? "🟡" : "🟢"}
                    </span>
                    <span className="font-semibold text-sm uppercase tracking-wide text-slate-800">
                      {riskAssessment.level === "high_risk" ? "High Risk" : riskAssessment.level === "caution" ? "Caution" : "Clear"}
                    </span>
                    <span className="ml-auto text-xs text-gray-400">Credit Intelligence</span>
                  </div>

                  {/* Key metrics row */}
                  <div className="flex gap-4 mb-3 text-sm">
                    <div>
                      <span className="text-gray-500">Outstanding</span>
                      <div className="font-medium text-slate-800">₹{riskAssessment.outstanding_balance.toLocaleString("en-IN")}</div>
                    </div>
                    <div>
                      <span className="text-gray-500">Credit Used</span>
                      <div className="font-medium text-slate-800">{riskAssessment.credit_utilisation_pct}%</div>
                    </div>
                    {riskAssessment.overdue_days > 0 && (
                      <div>
                        <span className="text-gray-500">Overdue</span>
                        <div className="font-medium text-red-600">{riskAssessment.overdue_days} days</div>
                      </div>
                    )}
                  </div>

                  {/* Signals */}
                  {riskAssessment.signals.length > 0 && (
                    <ul className="text-xs text-gray-600 mb-3 space-y-1">
                      {riskAssessment.signals.map((s: string, i: number) => (
                        <li key={i} className="flex items-center gap-1">
                          <span>⚠️</span> {s}
                        </li>
                      ))}
                    </ul>
                  )}

                  {/* Recommendation */}
                  <div className="bg-white rounded p-2 text-xs text-gray-700 border border-gray-100">
                    <span className="font-medium">💡 Recommendation: </span>
                    {riskAssessment.recommendation}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between gap-3 w-full">
                {selectedOrder && (selectedOrder.status === "Draft" || selectedOrder.status === "Pending" || selectedOrder.status === "Confirmed") && (
                  <button
                    onClick={() => setIsCancelDialogOpen(true)}
                    className="px-4 py-2.5 bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 text-sm font-bold rounded-lg transition-all cursor-pointer"
                  >
                    Cancel Order
                  </button>
                )}
                {selectedOrder && (selectedOrder.status === "Pending" || selectedOrder.status === "Needs Review") && (
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
                )}

                <div className="flex gap-2 flex-wrap">
                  {/* Download invoice — only for Confirmed */}
                  {selectedOrder && selectedOrder.status === "Confirmed" && (
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
                  )}

                  {/* Mark Delivered — only for Dispatched */}
                  {selectedOrder && selectedOrder.status === "Dispatched" && (
                    <button
                      onClick={handleMarkDelivered}
                      disabled={isMarkingDelivered}
                      className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 cursor-pointer"
                    >
                      {isMarkingDelivered ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Marking Delivered...</span>
                        </>
                      ) : (
                        <span>Mark as Delivered</span>
                      )}
                    </button>
                  )}

                  {/* Copy Payment Link — for any unpaid post-confirmation order */}
                  {selectedOrder &&
                    ["Confirmed", "Dispatched", "Delivered"].includes(selectedOrder.status) &&
                    selectedOrder.payment_status !== "PAID" && (
                      <button
                        onClick={async () => {
                          try {
                            const invoiceId = selectedOrderPayments?.invoice_id;
                            if (!invoiceId) {
                              showToast("No invoice found for this order.", "error");
                              return;
                            }

                            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
                            const res = await fetch(
                              `${apiBase}/api/v1/payments/payment-options?invoice_id=${invoiceId}&tenant_id=${activeTenantId}`
                            );
                            if (!res.ok) {
                              showToast("Failed to fetch payment options.", "error");
                              return;
                            }
                            const data = await res.json();
                            const link = data?.payment_links?.pay_invoice;

                            if (link) {
                              await navigator.clipboard.writeText(link);
                              showToast("Payment link copied to clipboard!", "success");
                            } else {
                              showToast("Payment link not available yet.", "error");
                            }
                          } catch (err) {
                            console.error("Failed to copy link:", err);
                            showToast("Failed to fetch payment link.", "error");
                          }
                        }}
                        className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 cursor-pointer"
                      >
                        <span>🔗</span>
                        <span>Copy Payment Link</span>
                      </button>
                    )}
                </div>
                <button
                  onClick={handleCloseDetails}
                  className="px-5 py-2.5 bg-slate-800 text-white hover:bg-slate-700 text-sm font-bold rounded-lg transition-all cursor-pointer"
                >
                  Close Details
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Order Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isCancelDialogOpen}
        title="Cancel Order"
        message={`Are you sure you want to cancel order ${selectedOrderNo}? This will reverse any reserved inventory and cannot be undone.`}
        confirmLabel="Yes, Cancel Order"
        cancelLabel="Keep Order"
        variant="danger"
        loading={isCancelling}
        onConfirm={handleCancelOrder}
        onCancel={() => setIsCancelDialogOpen(false)}
      />

      {/* Tally Export Date Range Modal */}
      {showTallyExportModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-fade-in">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-800">Export to Tally</h3>
              <button
                onClick={() => setShowTallyExportModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-50 transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-500 font-semibold mb-4">
              Downloads Confirmed/Dispatched/Delivered orders in this range as a Tally-importable
              XML (Sales Vouchers). Import via Gateway of Tally &rarr; Import Data &rarr; Vouchers.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-500 mb-1.5 uppercase tracking-wider">From</label>
                <input
                  type="date"
                  value={tallyStartDate}
                  onChange={(e) => setTallyStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-500 mb-1.5 uppercase tracking-wider">To</label>
                <input
                  type="date"
                  value={tallyEndDate}
                  onChange={(e) => setTallyEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
            {tallyExportError && (
              <div className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-100 rounded-lg text-rose-600 text-xs font-semibold mb-4">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{tallyExportError}</span>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowTallyExportModal(false)}
                className="px-4 py-2 text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded-lg transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleExportTally}
                className="px-4 py-2 bg-brand-blue hover:bg-brand-blueHover text-white rounded-lg text-xs font-bold transition-all cursor-pointer"
              >
                Download XML
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Action Sticky Progress Tracker Footer */}
      {bulkJobId && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 bg-white/95 backdrop-blur-md border border-slate-100 shadow-2xl p-6 rounded-2xl w-[450px] animate-slide-in pointer-events-auto flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-slate-800 text-sm">Bulk Invoice Download</h4>
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${bulkStatus === "COMPLETED"
              ? "bg-emerald-50 text-emerald-700 border border-emerald-100"
              : bulkStatus === "PARTIALLY_COMPLETED"
                ? "bg-amber-50 text-amber-700 border border-amber-100"
                : bulkStatus === "FAILED"
                  ? "bg-rose-50 text-rose-700 border border-rose-100"
                  : "bg-blue-50 text-brand-blue border border-blue-100 animate-pulse"
              }`}>
              {bulkStatus}
            </span>
          </div>

          {/* Progress Bar Component */}
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${bulkStatus === "FAILED" ? "bg-rose-500" : "bg-brand-blue"
                }`}
              style={{ width: `${bulkProgress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 font-bold uppercase tracking-wider">
            <span>Progress: {bulkProgress}%</span>
            {bulkStatus === "PROCESSING" && <span className="animate-pulse">Generating PDFs...</span>}
          </div>

          {/* Download Action Links / Failed lists */}
          <div className="flex flex-col gap-2">
            {(bulkStatus === "COMPLETED" || bulkStatus === "PARTIALLY_COMPLETED") && bulkResultLink && (
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}${bulkResultLink}`}
                download
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer shadow-sm text-center"
              >
                <span>📥 Download Invoices ZIP</span>
              </a>
            )}

            {bulkFailedOrders && bulkFailedOrders.length > 0 && (
              <div className="max-h-24 overflow-y-auto bg-rose-50/50 border border-rose-100/50 rounded-lg p-2.5 text-[10px] text-rose-700 font-medium space-y-1">
                <p className="font-bold uppercase tracking-wider text-[9px] text-rose-800">Failed Orders ({bulkFailedOrders.length}):</p>
                {bulkFailedOrders.map((fail, idx) => (
                  <div key={idx} className="flex justify-between font-mono">
                    <span>{fail.order_id.slice(0, 8)}...</span>
                    <span className="italic font-sans text-right truncate max-w-[200px]">{fail.error}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Close tracker */}
            {!isBulkProcessing && (
              <button
                onClick={() => {
                  setBulkJobId(null);
                  setBulkStatus(null);
                  setBulkProgress(0);
                  setBulkResultLink(null);
                  setBulkFailedOrders(null);
                }}
                className="w-full py-2 bg-slate-800 text-white hover:bg-slate-700 font-bold text-xs rounded-lg transition-all cursor-pointer text-center"
              >
                Close Tracking
              </button>
            )}
          </div>
        </div>
      )}

      {/* Toast Notification Queue — supports multiple concurrent messages */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      <PlaceOrderModal
        activeTenantId={activeTenantId}
        isOpen={isPlaceOrderOpen}
        onClose={() => setIsPlaceOrderOpen(false)}
        onSuccess={() => {
          setIsPlaceOrderOpen(false);
          if (activeTenantId) {
            fetchOrders(activeTenantId);
          }
        }}
      />
    </div>
  );
}
