"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Link from "next/link";
import { useDebounce } from "@/lib/debounce";
import {
  Search,
  MessageSquare,
  Send,
  Check,
  CheckCheck,
  Loader2,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  X,
  Bot,
  ExternalLink,
  ShieldCheck,
  Zap,
  ArrowRight
} from "lucide-react";

interface Customer {
  id: string;
  customer_id: string;
  retailer_name: string;
  address_text: string;
  gstin: string;
  tax_group: string;
  payment_terms: string;
  phone: string;
  credit_limit: number;
  outstanding_balance: number;
}

interface Message {
  id: number;
  text: string;
  sender: "customer" | "operator";
  timestamp: string;
}

interface ThreadItem {
  id: string;
  sku_id: string;
  product_name: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface ThreadOrder {
  id: string;
  order_id: string;
  status: string;
  source: string;
  created_on: string;
  invoice_type: string;
}

interface CustomerThread {
  order: ThreadOrder | null;
  items: ThreadItem[];
  total: number;
  has_unmatched: boolean;
}

export default function MessagesPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [loading, setLoading] = useState(true);

  const [chatStreams, setChatStreams] = useState<Record<string, Message[]>>({});
  const [unreadStates, setUnreadStates] = useState<Record<string, number>>({});
  const [inputText, setInputText] = useState("");

  // Real WhatsApp-ingested order for the selected customer (replaces mock extraction).
  const [thread, setThread] = useState<CustomerThread | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);

  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [confirmedOrderIds, setConfirmedOrderIds] = useState<Record<string, boolean>>({});

  // Triage state variables
  const [activeFeedTab, setActiveFeedTab] = useState<"inbox" | "triage">("inbox");
  const [orders, setOrders] = useState<any[]>([]);
  const [productsList, setProductsList] = useState<any[]>([]);
  const [selectedTriageOrderId, setSelectedTriageOrderId] = useState<string | null>(null);
  const [triageOrderDetails, setTriageOrderDetails] = useState<any[] | null>(null);
  const [loadingTriageDetails, setLoadingTriageDetails] = useState(false);
  const [resolvingTriageItemId, setResolvingTriageItemId] = useState<string | null>(null);

  // Fetch orders and products for triage
  const fetchTriageData = useCallback(async () => {
    if (!activeTenantId) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

      // Fetch orders
      const ordersResp = await fetch(`${apiBase}/api/v1/orders?tenant_id=${activeTenantId}&limit=200`, {
        credentials: "include"
      });
      if (ordersResp.ok) {
        const ordersData = await ordersResp.json();
        setOrders(ordersData.items ?? ordersData);
      }

      // Fetch products catalog
      const productsResp = await fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}&limit=200`, {
        credentials: "include"
      });
      if (productsResp.ok) {
        const productsData = await productsResp.json();
        setProductsList(productsData.items ?? productsData);
      }
    } catch (err) {
      console.error("Failed to fetch triage data:", err);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchTriageData();
  }, [fetchTriageData]);

  const fetchTriageOrderDetails = async (orderId: string) => {
    setLoadingTriageDetails(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/dashboard/order-details/${orderId}`, {
        credentials: "include"
      });
      if (resp.ok) {
        const data = await resp.json();
        setTriageOrderDetails(data);
        setSelectedTriageOrderId(orderId);
      }
    } catch (err) {
      console.error("Failed to load triage order details:", err);
      showToast("Error loading triage order details.", "error");
    } finally {
      setLoadingTriageDetails(false);
    }
  };

  const handleResolveTriageItem = async (itemId: string, skuCode: string, quantity: number) => {
    setResolvingTriageItemId(itemId);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/orders/items/${itemId}/resolve`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku_code: skuCode,
          quantity: quantity
        })
      });

      if (resp.ok) {
        showToast("Order line item resolved successfully!", "success");
        // Re-fetch triage data and order details
        await fetchTriageData();
        if (selectedTriageOrderId) {
          await fetchTriageOrderDetails(selectedTriageOrderId);
        }
      } else {
        const data = await resp.json();
        showToast(data.detail || "Failed to resolve item.", "error");
      }
    } catch (err) {
      console.error("Resolve error:", err);
      showToast("Connection failure during item resolution.", "error");
    } finally {
      setResolvingTriageItemId(null);
    }
  };

  const handleSelectTriageOrder = (order: any) => {
    const match = customers.find(c => c.retailer_name === order.customer);
    if (match) {
      handleSelectCustomer(match);
    }
    fetchTriageOrderDetails(order.id);
  };

  const [toast, setToast] = useState<{ show: boolean; message: string; type: "success" | "error" }>({
    show: false,
    message: "",
    type: "success"
  });

  const chatEndRef = useRef<HTMLDivElement>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast(prev => ({ ...prev, show: false }));
    }, 4500);
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

  // Fetch B2B Retailers / Customers
  const fetchCustomers = useCallback(async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/dashboard/customers?tenant_id=${activeTenantId}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to fetch customers");
      const data = await resp.json();
      setCustomers(data);

      // Auto-select first customer (prefer Kaveri)
      if (data.length > 0) {
        const kaveri = data.find((c: Customer) => c.retailer_name.toLowerCase().includes("kaveri"));
        setSelectedCustomer(kaveri || data[0]);
      } else {
        setSelectedCustomer(null);
      }
    } catch (err: any) {
      console.error(err);
      showToast("Failed to load customer list.", "error");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  // Fetch the real WhatsApp-ingested order thread when the selected customer changes.
  useEffect(() => {
    if (!selectedCustomer || !activeTenantId) {
      setThread(null);
      return;
    }
    let cancelled = false;
    const loadThread = async () => {
      setThreadLoading(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(
          `${apiBase}/api/v1/dashboard/customer-whatsapp-thread/${selectedCustomer.id}?tenant_id=${activeTenantId}`,
          { credentials: "include" }
        );
        if (!resp.ok) throw new Error("Failed to load thread");
        const data: CustomerThread = await resp.json();
        if (!cancelled) setThread(data);
      } catch (err) {
        console.error("Failed to load customer thread:", err);
        if (!cancelled) setThread({ order: null, items: [], total: 0, has_unmatched: false });
      } finally {
        if (!cancelled) setThreadLoading(false);
      }
    };
    loadThread();
    return () => {
      cancelled = true;
    };
  }, [selectedCustomer, activeTenantId]);

  // Scroll to bottom of chat
  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [selectedCustomer, chatStreams]);

  // Clear unread badge on click
  const handleSelectCustomer = (cust: Customer) => {
    setSelectedCustomer(cust);
    setUnreadStates(prev => ({
      ...prev,
      [cust.id]: 0
    }));
  };

  // Send Operator message
  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim() || !selectedCustomer) return;

    const newMessage: Message = {
      id: Date.now(),
      text: inputText,
      sender: "operator",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatStreams(prev => ({
      ...prev,
      [selectedCustomer.id]: [...(prev[selectedCustomer.id] || []), newMessage]
    }));

    setInputText("");
  };

  // Confirm the existing WhatsApp-ingested order (Draft -> Confirmed).
  const handleConfirmOrder = async () => {
    if (!thread?.order) return;
    const order = thread.order;

    if (thread.has_unmatched) {
      showToast("Resolve unmatched SKUs in the Triage Queue before confirming.", "error");
      return;
    }

    setSubmittingOrder(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const response = await fetch(`${apiBase}/api/v1/orders/${order.id}/confirm`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });

      const result = await response.json();

      if (response.ok && result.status === "success") {
        showToast(`Order ${order.order_id} confirmed.`, "success");
        setConfirmedOrderIds(prev => ({ ...prev, [order.id]: true }));
        setTimeout(() => fetchTriageData(), 50);
      } else {
        showToast(result.detail || "Order confirmation failed.", "error");
      }
    } catch (err: any) {
      console.error(err);
      showToast("Network failure during order confirmation.", "error");
    } finally {
      setSubmittingOrder(false);
    }
  };

  // Filter customers by search
  const filteredCustomers = customers.filter(c =>
    c.retailer_name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
    c.phone.includes(debouncedSearchQuery)
  );

  // Synthesize a chat bubble from the real ingested order, then append operator-typed messages.
  const syntheticMessages: Message[] = thread?.order
    ? [{
      id: -1,
      sender: "customer",
      timestamp: thread.order.created_on,
      text:
        `Order ${thread.order.order_id} received via WhatsApp:\n` +
        thread.items.map(it => `• ${it.quantity} × ${it.product_name}`).join("\n")
    }]
    : [];
  const operatorMessages = selectedCustomer ? chatStreams[selectedCustomer.id] || [] : [];
  const activeMessages = [...syntheticMessages, ...operatorMessages];

  const activeOrder = thread?.order || null;
  const activeItems = thread?.items || [];
  const orderTotal = thread?.total || 0;
  const matchedCount = activeItems.filter(it => it.sku_id !== "UNMATCHED_SKU" && it.sku_id !== "UNMATCHED_TRIAGE_SKU").length;
  const isConfirmed = activeOrder
    ? (confirmedOrderIds[activeOrder.id] || activeOrder.status === "Confirmed")
    : false;

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-dashboard-inset">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-slate-50 dark:bg-dashboard-inset min-h-screen text-slate-800 dark:text-slate-100 font-figtree overflow-x-auto">
      {/* Sidebar panel */}
      <Sidebar
        activeTab="Messages"
        setActiveTab={() => { }}
        tenantName={getTenantName()}
      />

      {/* Main viewport */}
      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">

        {/* Top bar */}
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        {/* Three-pane layout cockpit wrapper */}
        <div className="flex flex-1 overflow-hidden mt-16 min-w-[1024px]">

          {/* Panel 1: Left Pane (Retailers List) */}
          <div className="w-80 border-r border-slate-200 dark:border-white/10 bg-white dark:bg-dashboard-card flex flex-col h-full shadow-sm">
            <div className="p-4 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
              <h2 className="font-bold text-lg text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <span>Retailer Inbox</span>
              </h2>
              {customers.length > 0 && (
                <span className="bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  {customers.length} shops
                </span>
              )}
            </div>

            {/* Search Input */}
            <div className="p-3 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-dashboard-inset">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by shop name or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-white/10 rounded-xl text-xs font-medium bg-white dark:bg-dashboard-card text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all"
                />
              </div>
            </div>

            {/* Feed Tab Bar */}
            <div className="flex border-b border-slate-100 dark:border-white/5 bg-white dark:bg-dashboard-card">
              <button
                onClick={() => setActiveFeedTab("inbox")}
                className={`flex-1 text-center py-2.5 text-xs font-bold border-b-2 transition-all ${activeFeedTab === "inbox"
                    ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
                    : "border-transparent text-slate-400 hover:text-slate-600"
                  }`}
              >
                Inbox
              </button>
              <button
                onClick={() => setActiveFeedTab("triage")}
                className={`flex-1 text-center py-2.5 text-xs font-bold border-b-2 transition-all flex items-center justify-center gap-1.5 ${activeFeedTab === "triage"
                    ? "border-rose-500 text-rose-600 dark:text-rose-400"
                    : "border-transparent text-slate-400 hover:text-slate-600"
                  }`}
              >
                <span>Triage Queue</span>
                {orders.filter(o => o.status === "Needs Review").length > 0 && (
                  <span className="bg-rose-500 text-white text-[9px] font-extrabold px-1.5 py-0.5 rounded-full shrink-0">
                    {orders.filter(o => o.status === "Needs Review").length}
                  </span>
                )}
              </button>
            </div>

            {/* Customers list container */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
              {activeFeedTab === "inbox" ? (
                loading ? (
                  <div className="flex flex-col items-center justify-center py-12 gap-3">
                    <Loader2 className="w-6 h-6 text-brand-blue animate-spin" />
                    <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold">Loading Retailers...</span>
                  </div>
                ) : filteredCustomers.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                    <AlertCircle className="w-8 h-8 mb-2" />
                    <span className="text-xs font-medium">No retailers found</span>
                  </div>
                ) : (
                  filteredCustomers.map((c) => {
                    const isSelected = selectedCustomer?.id === c.id;
                    const unread = unreadStates[c.id] || 0;
                    const lastMessage = chatStreams[c.id]?.length
                      ? chatStreams[c.id][chatStreams[c.id].length - 1].text
                      : "No messages yet";

                    return (
                      <button
                        key={c.id}
                        onClick={() => handleSelectCustomer(c)}
                        className={`w-full text-left p-4 transition-all duration-200 flex gap-3 ${isSelected
                            ? "bg-slate-50 dark:bg-dashboard-inset border-l-4 border-brand-blue"
                            : "hover:bg-slate-50/60 dark:hover:bg-white/5 border-l-4 border-transparent"
                          }`}
                      >
                        {/* Avatar */}
                        <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-white/5 flex items-center justify-center font-bold text-slate-600 dark:text-slate-400 text-sm border border-slate-200 dark:border-white/10 shadow-sm flex-shrink-0">
                          {c.retailer_name.substring(0, 2).toUpperCase()}
                        </div>

                        {/* Info & Last Msg */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <h4 className="font-semibold text-xs text-slate-800 dark:text-slate-100 truncate">
                              {c.retailer_name}
                            </h4>
                            {unread > 0 && (
                              <span className="bg-emerald-500 text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center animate-bounce">
                                {unread}
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-slate-400 font-semibold mt-0.5 truncate">
                            {c.phone}
                          </p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium mt-1 truncate">
                            {lastMessage}
                          </p>
                          <div className="flex items-center justify-between mt-1 text-[9px] font-semibold">
                            <span className="text-slate-400">Bal: ₹{c.outstanding_balance.toLocaleString()}</span>
                            <span className="text-slate-400">Terms: {c.payment_terms}</span>
                          </div>
                        </div>
                      </button>
                    );
                  })
                )
              ) : (
                // Triage Feed Tab list
                orders.filter(o => o.status === "Needs Review").length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                    <CheckCircle2 className="w-8 h-8 mb-2 text-emerald-500" />
                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Triage Queue is Clean!</span>
                  </div>
                ) : (
                  orders.filter(o => o.status === "Needs Review").map((o) => {
                    const isSelected = selectedTriageOrderId === o.id;
                    return (
                      <button
                        key={o.id}
                        onClick={() => handleSelectTriageOrder(o)}
                        className={`w-full text-left p-4 transition-all duration-200 border-l-4 ${isSelected
                            ? "bg-rose-50/50 dark:bg-rose-500/[0.08] border-rose-500"
                            : "hover:bg-rose-50/20 border-transparent"
                          }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-full bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 flex items-center justify-center font-bold text-rose-600 dark:text-rose-400 text-xs shrink-0">
                            TRG
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-center">
                              <h4 className="font-bold text-xs text-slate-800 dark:text-slate-100 truncate">{o.customer}</h4>
                              <span className="text-[9px] font-bold bg-rose-100 dark:bg-rose-500/15 text-rose-800 dark:text-rose-300 px-1.5 py-0.5 rounded border border-rose-200 dark:border-rose-500/20">
                                Review
                              </span>
                            </div>
                            <p className="text-[10px] text-brand-blue font-bold mt-1">
                              {o.order_id}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold mt-1">
                              Amount: ₹{o.amount.toLocaleString([], { minimumFractionDigits: 2 })}
                            </p>
                            <p className="text-[9px] text-slate-400 font-semibold mt-1">
                              {o.created_on}
                            </p>
                          </div>
                        </div>
                      </button>
                    );
                  })
                )
              )}
            </div>
          </div>

          {/* Panel 2: Middle Pane (WhatsApp Chat Stream) */}
          <div className="flex-1 bg-[#efeae2] dark:bg-dashboard-bg flex flex-col h-full border-r border-slate-200 dark:border-white/10 relative">
            {selectedCustomer ? (
              <>
                {/* Chat Header */}
                <div className="bg-white dark:bg-dashboard-card border-b border-slate-200 dark:border-white/10 p-4 flex items-center justify-between shadow-sm z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-brand-blue flex items-center justify-center font-bold text-white text-sm">
                      {selectedCustomer.retailer_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100">{selectedCustomer.retailer_name}</h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span className="text-[10px] text-slate-400 font-bold">Active Now</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 px-2.5 py-1 rounded-full font-bold">
                      {selectedCustomer.customer_id}
                    </span>
                  </div>
                </div>

                {/* Chat Messages Log */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 flex flex-col">
                  {/* WhatsApp background pattern (represented by CSS styling of this div) */}
                  <div className="text-center my-2">
                    <span className="bg-slate-200/80 dark:bg-white/10 text-slate-600 dark:text-slate-400 text-[10px] font-bold px-3 py-1 rounded-lg">
                      TODAY
                    </span>
                  </div>

                  {!threadLoading && activeMessages.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-10">
                      <MessageSquare className="w-8 h-8" />
                      <p className="text-xs font-semibold">No WhatsApp orders ingested for this retailer yet.</p>
                    </div>
                  )}

                  {activeMessages.map((msg, index) => {
                    const isOp = msg.sender === "operator";
                    return (
                      <div
                        key={msg.id || index}
                        className={`flex flex-col max-w-[70%] rounded-2xl p-3 text-xs shadow-sm relative transition-all duration-200 ${isOp
                            ? "bg-[#d9fdd3] dark:bg-emerald-900/30 text-slate-800 dark:text-slate-100 self-end rounded-tr-none border border-emerald-100 dark:border-emerald-500/20"
                            : "bg-white dark:bg-dashboard-card text-slate-800 dark:text-slate-100 self-start rounded-tl-none border border-slate-200 dark:border-white/10"
                          }`}
                      >
                        {/* Sender Label */}
                        <span className={`text-[9px] font-bold mb-1 block uppercase tracking-wider ${isOp ? "text-emerald-700 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400"
                          }`}>
                          {isOp ? "OPERATOR" : "CUSTOMER"}
                        </span>

                        <p className="font-medium whitespace-pre-wrap leading-relaxed">
                          {msg.text}
                        </p>

                        {/* Timestamp & double checkmarks */}
                        <div className="flex items-center justify-end gap-1 mt-1 text-[9px] text-slate-400 font-semibold">
                          <span>{msg.timestamp}</span>
                          {isOp && <CheckCheck className="w-3.5 h-3.5 text-blue-500" />}
                        </div>
                      </div>
                    );
                  })}
                  <div ref={chatEndRef} />
                </div>

                {/* Chat Input panel */}
                <form
                  onSubmit={handleSendMessage}
                  className="bg-white dark:bg-dashboard-card border-t border-slate-200 dark:border-white/10 p-4 flex items-center gap-3 shadow-md z-10"
                >
                  <input
                    type="text"
                    placeholder="Type an operator message to B2B retailer..."
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    className="flex-1 px-4 py-3 border border-slate-200 dark:border-white/10 rounded-xl text-xs font-medium bg-white dark:bg-dashboard-inset text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-blue"
                  />
                  <button
                    type="submit"
                    className="bg-emerald-500 hover:bg-emerald-600 text-white p-3 rounded-xl shadow transition-all duration-200 hover:scale-105 active:scale-95 flex items-center justify-center"
                  >
                    <Send className="w-4.5 h-4.5" />
                  </button>
                </form>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3">
                <MessageSquare className="w-12 h-12" />
                <p className="text-sm font-semibold">Select a retailer from the feed to load communication logs</p>
              </div>
            )}
          </div>

          {/* Panel 3: Right Pane (AI Order Ingestion Engine) */}
          <div className="w-96 bg-white dark:bg-dashboard-card flex flex-col h-full overflow-y-auto border-l border-slate-200 dark:border-white/10">
            {activeFeedTab === "triage" && selectedTriageOrderId ? (
              // Triage Resolution Pane
              <div className="flex flex-col h-full">
                <div className="bg-gradient-to-r from-rose-50 to-orange-50 dark:from-rose-500/10 dark:to-orange-500/10 border-b border-rose-100 dark:border-rose-500/20 p-4">
                  <div className="flex items-center gap-2 text-rose-800 dark:text-rose-300">
                    <div className="w-8 h-8 rounded-lg bg-rose-500 text-white flex items-center justify-center">
                      <AlertCircle className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm">Order SKU Resolution</h3>
                      <p className="text-[10px] text-rose-600 dark:text-rose-400 font-semibold mt-0.5">
                        Assign unmatched SKUs to catalog items in one click.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="p-4 space-y-5 flex-1">
                  {loadingTriageDetails ? (
                    <div className="flex flex-col items-center justify-center py-20 space-y-3">
                      <Loader2 className="w-6 h-6 text-rose-500 animate-spin" />
                      <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold">Loading line items...</span>
                    </div>
                  ) : triageOrderDetails ? (
                    <div className="space-y-4">
                      <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-3.5 space-y-2">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-slate-400">Retailer</span>
                          <span className="font-bold text-slate-700 dark:text-slate-300">{selectedCustomer?.retailer_name}</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-slate-400">Order ID</span>
                          <span className="font-extrabold text-brand-blue">{orders.find(o => o.id === selectedTriageOrderId)?.order_id}</span>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                          Line Items
                        </label>
                        {triageOrderDetails.map((item, idx) => {
                          const isUnmatched = item.sku_id === "UNMATCHED_SKU" || item.sku_id === "UNMATCHED_TRIAGE_SKU";
                          return (
                            <div key={idx} className="p-4 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-dashboard-inset flex flex-col gap-2">
                              <div className="flex items-start justify-between">
                                <div className="flex-1 pr-4">
                                  {isUnmatched ? (
                                    <div className="space-y-2">
                                      <p className="font-bold text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1">
                                        <AlertCircle className="w-4 h-4 shrink-0 animate-pulse" />
                                        <span>Unmatched Line Item</span>
                                      </p>
                                      <p className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold leading-relaxed">
                                        Original Input: <span className="italic font-bold text-slate-700 dark:text-slate-300">"{item.brand}"</span>
                                      </p>

                                      <label className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide">Map to Catalog SKU</label>
                                      <select
                                        disabled={resolvingTriageItemId === item.id}
                                        onChange={(e) => {
                                          if (e.target.value) {
                                            handleResolveTriageItem(item.id, e.target.value, item.quantity);
                                          }
                                        }}
                                        className="w-full mt-1 p-2 border border-rose-200 dark:border-rose-500/20 rounded-lg text-xs bg-white dark:bg-dashboard-card text-slate-700 dark:text-slate-300 font-semibold focus:outline-none focus:ring-1 focus:ring-rose-500 cursor-pointer"
                                      >
                                        <option value="">-- Select SKU --</option>
                                        {productsList.map((p) => (
                                          <option key={p.id} value={p.sku_id}>
                                            {p.sku_id} - {p.brand} {p.category} ({p.pack_size})
                                          </option>
                                        ))}
                                      </select>
                                    </div>
                                  ) : (
                                    <>
                                      <p className="font-bold text-xs text-slate-800 dark:text-slate-100">{item.brand} SKU</p>
                                      <p className="text-[10px] text-slate-400 font-semibold">{item.sku_id} ({item.pack_size})</p>
                                      <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300 mt-1">₹{item.total_price.toLocaleString([], { minimumFractionDigits: 2 })}</p>
                                    </>
                                  )}
                                </div>
                                <div className="flex flex-col items-end shrink-0">
                                  <span className="text-[10px] font-extrabold bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 px-2 py-0.5 rounded-full">Qty: {item.quantity}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-10 text-slate-400 font-semibold">Select a triage order to view line items</div>
                  )}
                </div>
              </div>
            ) : threadLoading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-400">
                <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
                <span className="text-xs font-semibold">Loading ingested order...</span>
              </div>
            ) : selectedCustomer && activeOrder ? (
              // Normal AI Extraction Pane
              <div className="flex flex-col h-full">
                {/* AI Banner Header */}
                <div className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-500/10 dark:to-teal-500/10 border-b border-emerald-100 dark:border-emerald-500/20 p-4">
                  <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500 text-white flex items-center justify-center">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm">Gemini AI Ingested Order</h3>
                      <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 mt-0.5">
                        <Sparkles className="w-3 h-3 animate-pulse" />
                        <span>{activeOrder.order_id} · {activeOrder.created_on}</span>
                      </p>
                    </div>
                  </div>
                </div>

                {/* Extraction Body */}
                <div className="p-4 space-y-5 flex-1">

                  {/* Scope details */}
                  <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-100 dark:border-white/5 rounded-xl p-3.5 space-y-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Customer Shop</span>
                      <span className="font-bold text-slate-700 dark:text-slate-300">{selectedCustomer.retailer_name}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Ingestion Channel</span>
                      <span className="bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 font-bold px-2 py-0.5 rounded border border-emerald-100 dark:border-emerald-500/20 text-[10px] flex items-center gap-1">
                        <Zap className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                        <span>WhatsApp Webhook</span>
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Order Status</span>
                      <span className={`font-bold px-2 py-0.5 rounded border text-[10px] ${activeOrder.status === "Confirmed"
                          ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-100 dark:border-emerald-500/20"
                          : thread?.has_unmatched
                            ? "bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-100 dark:border-rose-500/20"
                            : "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-100 dark:border-amber-500/20"
                        }`}>
                        {activeOrder.status}
                      </span>
                    </div>
                  </div>

                  {/* Structured SKU Table */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Extracted Order Line Items
                    </label>
                    <div className="border border-slate-200 dark:border-white/10 rounded-xl overflow-hidden shadow-sm">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="bg-slate-50 dark:bg-dashboard-inset border-b border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400 font-bold text-[10px] uppercase">
                            <th className="py-2.5 px-3">Item / SKU</th>
                            <th className="py-2.5 px-2 text-center">Qty</th>
                            <th className="py-2.5 px-3 text-right">Price</th>
                            <th className="py-2.5 px-3 text-right">Subtotal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                          {activeItems.map((item, index) => {
                            const isUnmatched = item.sku_id === "UNMATCHED_SKU" || item.sku_id === "UNMATCHED_TRIAGE_SKU";
                            return (
                              <tr key={item.id || index} className="hover:bg-slate-50/50 dark:hover:bg-white/5 font-medium">
                                <td className="py-2.5 px-3">
                                  <p className={`font-bold ${isUnmatched ? "text-rose-600 dark:text-rose-400" : "text-slate-700 dark:text-slate-300"}`}>
                                    {isUnmatched ? "Unmatched item" : item.product_name}
                                  </p>
                                  <p className="text-[9px] text-slate-400 font-semibold">
                                    {isUnmatched ? "Needs triage" : item.sku_id}
                                  </p>
                                </td>
                                <td className="py-2.5 px-2 text-center text-slate-600 dark:text-slate-400">
                                  {item.quantity}
                                </td>
                                <td className="py-2.5 px-3 text-right text-slate-500 dark:text-slate-400">
                                  ₹{item.unit_price.toFixed(2)}
                                </td>
                                <td className="py-2.5 px-3 text-right font-bold text-slate-700 dark:text-slate-300">
                                  ₹{item.total_price.toLocaleString([], { minimumFractionDigits: 2 })}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                        <tfoot>
                          <tr className="bg-slate-50/80 dark:bg-white/10 font-bold border-t border-slate-200 dark:border-white/10">
                            <td colSpan={3} className="py-3 px-3 text-slate-600 dark:text-slate-400">Total Extracted Value</td>
                            <td className="py-3 px-3 text-right text-brand-blue font-extrabold text-sm">
                              ₹{orderTotal.toLocaleString([], { minimumFractionDigits: 2 })}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </div>

                  {/* Validation Metrics */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Catalog Resolution
                    </label>
                    <div className="space-y-2">
                      <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200 dark:border-white/10 rounded-xl p-3 flex items-center justify-between text-xs font-semibold">
                        <div className="flex items-center gap-2">
                          {thread?.has_unmatched ? (
                            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                          ) : (
                            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                          )}
                          <span className="text-slate-600 dark:text-slate-400">SKU Catalog Match</span>
                        </div>
                        <span className={`font-bold px-2 py-0.5 rounded border text-[10px] ${thread?.has_unmatched
                            ? "text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 border-rose-100 dark:border-rose-500/20"
                            : "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-100 dark:border-emerald-500/20"
                          }`}>
                          {matchedCount}/{activeItems.length} resolved
                        </span>
                      </div>

                      {thread?.has_unmatched && (
                        <button
                          onClick={() => { setActiveFeedTab("triage"); handleSelectTriageOrder({ id: activeOrder.id, customer: selectedCustomer?.retailer_name }); }}
                          className="w-full bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 border border-rose-200 dark:border-rose-500/20 rounded-xl p-3 flex items-center justify-between text-xs font-bold text-rose-700 dark:text-rose-400 transition-all"
                        >
                          <span>Resolve unmatched SKUs in Triage</span>
                          <ArrowRight className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Confirm action */}
                <div className="p-4 border-t border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-dashboard-inset">
                  {isConfirmed ? (
                    <div className="bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl p-4 text-center space-y-3">
                      <div className="flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400 font-bold text-xs uppercase tracking-wide">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        <span>Order Confirmed</span>
                      </div>
                      <div className="text-sm font-extrabold text-brand-blue bg-white dark:bg-dashboard-card p-2 rounded-lg border border-slate-200 dark:border-white/10 shadow-sm flex items-center justify-center gap-2">
                        <span>{activeOrder.order_id}</span>
                        <Link href="/dashboard/orders" className="text-slate-400 hover:text-brand-blue" title="Go to Orders Grid">
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                      </div>
                      <p className="text-[10px] text-slate-400 font-semibold">
                        Ready for billing & fulfillment processing.
                      </p>
                    </div>
                  ) : (
                    <button
                      onClick={handleConfirmOrder}
                      disabled={submittingOrder || thread?.has_unmatched}
                      className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-bold py-3 px-6 rounded-xl shadow-lg hover:shadow-emerald-100 transition-all duration-300 transform active:scale-95 flex items-center justify-center gap-2 border border-emerald-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {submittingOrder ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Confirming Order...</span>
                        </>
                      ) : (
                        <>
                          <Bot className="w-4 h-4" />
                          <span>{thread?.has_unmatched ? "Resolve Triage First" : "Confirm Order"}</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 p-6 text-center gap-3">
                <Bot className="w-12 h-12 text-slate-300" />
                <h4 className="font-bold text-sm text-slate-600 dark:text-slate-400">No Ingested Order</h4>
                <p className="text-xs font-semibold leading-relaxed max-w-[200px]">
                  This retailer has no WhatsApp-ingested order yet. Orders captured via the WhatsApp webhook will appear here.
                </p>
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Local Toast UI notification */}
      {toast.show && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 ${toast.type === "success"
            ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/20"
            : "bg-rose-50 dark:bg-rose-500/10 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-500/20"
          }`}>
          {toast.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400" />
          )}
          <span className="text-sm font-semibold">{toast.message}</span>
          <button onClick={() => setToast(prev => ({ ...prev, show: false }))} className="text-slate-400 hover:text-slate-600 ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
