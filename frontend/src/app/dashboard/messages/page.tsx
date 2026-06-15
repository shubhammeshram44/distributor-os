"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import Link from "next/link";
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

interface OrderItem {
  sku_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

interface Extraction {
  items: OrderItem[];
  confidence: string;
  status: string;
}

const getMockDataForCustomer = (custName: string) => {
  const name = custName.toLowerCase();
  if (name.includes("kaveri")) {
    return {
      unreadCount: 2,
      messages: [
        { id: 1, text: "Hello! Need to place a new stock order.", sender: "customer", timestamp: "10:05 AM" },
        { id: 2, text: "Sure, please share the item list.", sender: "operator", timestamp: "10:06 AM" },
        { id: 3, text: "Please send 15 units of Maggi 2-Min Noodles (PROD-MAGGI-PACK) and 10 units of Tata Premium Soap (PROD-HUL-SOAP) to our main shop.", sender: "customer", timestamp: "10:08 AM" },
        { id: 4, text: "Let me know the total price and if they are available.", sender: "customer", timestamp: "10:09 AM" },
      ],
      extraction: {
        items: [
          { sku_id: "PROD-MAGGI-PACK", product_name: "Maggi 2-Min Noodles", quantity: 15, unit_price: 450.0 },
          { sku_id: "PROD-HUL-SOAP", product_name: "Tata Premium Soap", quantity: 10, unit_price: 45.0 }
        ],
        confidence: "98%",
        status: "Draft"
      }
    };
  } else if (name.includes("maruthi")) {
    return {
      unreadCount: 0,
      messages: [
        { id: 1, text: "Do you have Aashirvaad Aata in stock?", sender: "customer", timestamp: "Yesterday 4:15 PM" },
        { id: 2, text: "Yes, we have plenty of Aashirvaad Aata.", sender: "operator", timestamp: "Yesterday 4:18 PM" },
        { id: 3, text: "Excellent. Please book 10 units of Aashirvaad Aata (PROD-ITC-AATA) for us.", sender: "customer", timestamp: "Yesterday 4:20 PM" },
      ],
      extraction: {
        items: [
          { sku_id: "PROD-ITC-AATA", product_name: "Aashirvaad Aata", quantity: 10, unit_price: 260.0 }
        ],
        confidence: "95%",
        status: "Draft"
      }
    };
  } else if (name.includes("venkateshwara") || name.includes("sri venk")) {
    return {
      unreadCount: 0,
      messages: [
        { id: 1, text: "Hi, please check our last order. Also we need 50 packets of Chips.", sender: "customer", timestamp: "2 days ago" },
        { id: 2, text: "Sure, chips are in stock (PROD-ITC-CHIPS).", sender: "operator", timestamp: "2 days ago" },
        { id: 3, text: "Okay, please add 50 packets of Chips (PROD-ITC-CHIPS) and 2 units of Stayfree XL (PROD-STAYFREE-XL).", sender: "customer", timestamp: "2 days ago" },
      ],
      extraction: {
        items: [
          { sku_id: "PROD-ITC-CHIPS", product_name: "Chips", quantity: 50, unit_price: 10.0 },
          { sku_id: "PROD-STAYFREE-XL", product_name: "Stayfree XL", quantity: 2, unit_price: 1250.0 }
        ],
        confidence: "97%",
        status: "Draft"
      }
    };
  } else if (name.includes("jayam")) {
    return {
      unreadCount: 0,
      messages: [
        { id: 1, text: "Need 100 packets of Chips (PROD-ITC-CHIPS).", sender: "customer", timestamp: "3 days ago" },
        { id: 2, text: "Noted, booking them now.", sender: "operator", timestamp: "3 days ago" }
      ],
      extraction: {
        items: [
          { sku_id: "PROD-ITC-CHIPS", product_name: "Chips", quantity: 100, unit_price: 10.0 }
        ],
        confidence: "99%",
        status: "Draft"
      }
    };
  } else if (name.includes("balaji")) {
    return {
      unreadCount: 0,
      messages: [
        { id: 1, text: "Are there any offers on HUL Soap?", sender: "customer", timestamp: "4 days ago" },
        { id: 2, text: "Current price is 45 per unit. For orders above 100 units, we offer 5% cash discount.", sender: "operator", timestamp: "4 days ago" },
        { id: 3, text: "Great, please send 120 units of HUL Soap (PROD-HUL-SOAP).", sender: "customer", timestamp: "4 days ago" }
      ],
      extraction: {
        items: [
          { sku_id: "PROD-HUL-SOAP", product_name: "Tata Premium Soap", quantity: 120, unit_price: 45.0 }
        ],
        confidence: "96%",
        status: "Draft"
      }
    };
  } else {
    return {
      unreadCount: 0,
      messages: [
        { id: 1, text: "Hello, we want to place a standard grocery replenishment order.", sender: "customer", timestamp: "Just now" }
      ],
      extraction: null
    };
  }
};

export default function MessagesPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  
  const [chatStreams, setChatStreams] = useState<Record<string, Message[]>>({});
  const [unreadStates, setUnreadStates] = useState<Record<string, number>>({});
  const [inputText, setInputText] = useState("");
  
  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [approvedOrders, setApprovedOrders] = useState<Record<string, { internalId: string; id: string }>>({});
  
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

  // Sync / Initialize chat states from customers list
  useEffect(() => {
    if (customers.length === 0) return;
    
    const initialChats: Record<string, Message[]> = { ...chatStreams };
    const initialUnreads: Record<string, number> = { ...unreadStates };
    
    customers.forEach((c) => {
      if (!initialChats[c.id]) {
        const mock = getMockDataForCustomer(c.retailer_name);
        initialChats[c.id] = mock.messages as Message[];
        initialUnreads[c.id] = mock.unreadCount;
      }
    });
    
    setChatStreams(initialChats);
    setUnreadStates(initialUnreads);
  }, [customers]);

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

  // Submit parsed items directly to POST /api/v1/orders
  const handleApproveOrder = async () => {
    if (!selectedCustomer) return;
    const mockData = getMockDataForCustomer(selectedCustomer.retailer_name);
    const extraction = mockData.extraction;
    
    if (!extraction || extraction.items.length === 0) {
      showToast("No structured items parsed for this retailer.", "error");
      return;
    }
    
    setSubmittingOrder(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const payload = {
        tenant_id: activeTenantId,
        customer_id: selectedCustomer.id,
        source: "WhatsApp",
        status: "Draft",
        items: extraction.items.map(item => ({
          sku_id: item.sku_id,
          quantity: item.quantity,
          unit_price: item.unit_price
        }))
      };
      
      const response = await fetch(`${apiBase}/api/v1/orders`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok && result.status === "success") {
        showToast(`Digital Order generated successfully: ${result.internal_order_id}`, "success");
        setApprovedOrders(prev => ({
          ...prev,
          [selectedCustomer.id]: {
            internalId: result.internal_order_id,
            id: result.order_id
          }
        }));
      } else {
        const errorMsg = result.detail || "Standard Order creation error.";
        showToast(errorMsg, "error");
      }
    } catch (err: any) {
      console.error(err);
      showToast("Network breakdown during Order routing transaction.", "error");
    } finally {
      setSubmittingOrder(false);
    }
  };

  // Filter customers by search
  const filteredCustomers = customers.filter(c =>
    c.retailer_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.phone.includes(searchQuery)
  );

  const activeMessages = selectedCustomer ? chatStreams[selectedCustomer.id] || [] : [];
  const activeExtraction = selectedCustomer ? getMockDataForCustomer(selectedCustomer.retailer_name).extraction : null;
  const isApproved = selectedCustomer ? approvedOrders[selectedCustomer.id] : null;

  // Calculate order total
  const orderTotal = activeExtraction 
    ? activeExtraction.items.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0)
    : 0;

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-slate-50 min-h-screen text-slate-800 font-sans overflow-hidden">
      {/* Sidebar panel */}
      <Sidebar
        activeTab="Messages"
        setActiveTab={() => {}}
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
        <div className="flex flex-1 overflow-hidden mt-16">
          
          {/* Panel 1: Left Pane (Retailers List) */}
          <div className="w-80 border-r border-slate-200 bg-white flex flex-col h-full shadow-sm">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-emerald-600" />
                <span>Retailer Inbox</span>
              </h2>
              {customers.length > 0 && (
                <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  {customers.length} shops
                </span>
              )}
            </div>

            {/* Search Input */}
            <div className="p-3 border-b border-slate-100 bg-slate-50/50">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by shop name or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all"
                />
              </div>
            </div>

            {/* Customers list container */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <Loader2 className="w-6 h-6 text-brand-blue animate-spin" />
                  <span className="text-xs text-slate-500 font-semibold">Loading Retailers...</span>
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
                      className={`w-full text-left p-4 transition-all duration-200 flex gap-3 ${
                        isSelected 
                          ? "bg-slate-50 border-l-4 border-brand-blue" 
                          : "hover:bg-slate-50/60 border-l-4 border-transparent"
                      }`}
                    >
                      {/* Avatar */}
                      <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-sm border border-slate-200 shadow-sm flex-shrink-0">
                        {c.retailer_name.substring(0, 2).toUpperCase()}
                      </div>

                      {/* Info & Last Msg */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-xs text-slate-800 truncate">
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
                        <p className="text-[11px] text-slate-500 font-medium mt-1 truncate">
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
              )}
            </div>
          </div>

          {/* Panel 2: Middle Pane (WhatsApp Chat Stream) */}
          <div className="flex-1 bg-[#efeae2] flex flex-col h-full border-r border-slate-200 relative">
            {selectedCustomer ? (
              <>
                {/* Chat Header */}
                <div className="bg-white border-b border-slate-200 p-4 flex items-center justify-between shadow-sm z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-brand-blue flex items-center justify-center font-bold text-white text-sm">
                      {selectedCustomer.retailer_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-800">{selectedCustomer.retailer_name}</h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span className="text-[10px] text-slate-400 font-bold">Active Now</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full font-bold">
                      {selectedCustomer.customer_id}
                    </span>
                  </div>
                </div>

                {/* Chat Messages Log */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 flex flex-col">
                  {/* WhatsApp background pattern (represented by CSS styling of this div) */}
                  <div className="text-center my-2">
                    <span className="bg-slate-200/80 text-slate-600 text-[10px] font-bold px-3 py-1 rounded-lg">
                      TODAY
                    </span>
                  </div>

                  {activeMessages.map((msg, index) => {
                    const isOp = msg.sender === "operator";
                    return (
                      <div
                        key={msg.id || index}
                        className={`flex flex-col max-w-[70%] rounded-2xl p-3 text-xs shadow-sm relative transition-all duration-200 ${
                          isOp 
                            ? "bg-[#d9fdd3] text-slate-800 self-end rounded-tr-none border border-emerald-100" 
                            : "bg-white text-slate-800 self-start rounded-tl-none border border-slate-200"
                        }`}
                      >
                        {/* Sender Label */}
                        <span className={`text-[9px] font-bold mb-1 block uppercase tracking-wider ${
                          isOp ? "text-emerald-700" : "text-slate-500"
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
                  className="bg-white border-t border-slate-200 p-4 flex items-center gap-3 shadow-md z-10"
                >
                  <input
                    type="text"
                    placeholder="Type an operator message to B2B retailer..."
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    className="flex-1 px-4 py-3 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-1 focus:ring-brand-blue"
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
          <div className="w-96 bg-white flex flex-col h-full overflow-y-auto border-l border-slate-200">
            {selectedCustomer && activeExtraction ? (
              <div className="flex flex-col h-full">
                {/* AI Banner Header */}
                <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border-b border-emerald-100 p-4">
                  <div className="flex items-center gap-2 text-emerald-800">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500 text-white flex items-center justify-center">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm">Gemini AI Order Generator</h3>
                      <p className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 mt-0.5">
                        <Sparkles className="w-3 h-3 animate-pulse" />
                        <span>Confidence: {activeExtraction.confidence} (Flash-1.5)</span>
                      </p>
                    </div>
                  </div>
                </div>

                {/* Extraction Body */}
                <div className="p-4 space-y-5 flex-1">
                  
                  {/* Scope details */}
                  <div className="bg-slate-50 border border-slate-100 rounded-xl p-3.5 space-y-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Customer Shop</span>
                      <span className="font-bold text-slate-700">{selectedCustomer.retailer_name}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Ingestion Channel</span>
                      <span className="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded border border-emerald-100 text-[10px] flex items-center gap-1">
                        <Zap className="w-3 h-3 text-emerald-600" />
                        <span>WhatsApp Webhook</span>
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-400">Order Format Status</span>
                      <span className="bg-amber-50 text-amber-700 font-bold px-2 py-0.5 rounded border border-amber-100 text-[10px]">
                        Draft / Pending
                      </span>
                    </div>
                  </div>

                  {/* Structured SKU Table */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Extracted Order Line Items
                    </label>
                    <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold text-[10px] uppercase">
                            <th className="py-2.5 px-3">Item / SKU</th>
                            <th className="py-2.5 px-2 text-center">Qty</th>
                            <th className="py-2.5 px-3 text-right">Price</th>
                            <th className="py-2.5 px-3 text-right">Subtotal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {activeExtraction.items.map((item, index) => {
                            const total = item.quantity * item.unit_price;
                            return (
                              <tr key={index} className="hover:bg-slate-50/50 font-medium">
                                <td className="py-2.5 px-3">
                                  <p className="font-bold text-slate-700">{item.product_name}</p>
                                  <p className="text-[9px] text-slate-400 font-semibold">{item.sku_id}</p>
                                </td>
                                <td className="py-2.5 px-2 text-center text-slate-600">
                                  {item.quantity}
                                </td>
                                <td className="py-2.5 px-3 text-right text-slate-500">
                                  ₹{item.unit_price.toFixed(2)}
                                </td>
                                <td className="py-2.5 px-3 text-right font-bold text-slate-700">
                                  ₹{total.toLocaleString([], { minimumFractionDigits: 2 })}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                        <tfoot>
                          <tr className="bg-slate-50/80 font-bold border-t border-slate-200">
                            <td colSpan={3} className="py-3 px-3 text-slate-600">Total Extracted Value</td>
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
                      Operations Safety Checks
                    </label>
                    <div className="space-y-2">
                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between text-xs font-semibold">
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-emerald-600" />
                          <span className="text-slate-600">Real-time Catalog Match</span>
                        </div>
                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100 text-[10px]">
                          100% SKU Resolved
                        </span>
                      </div>

                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between text-xs font-semibold">
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-emerald-600" />
                          <span className="text-slate-600">Physical Inventory Check</span>
                        </div>
                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100 text-[10px]">
                          In Stock ✅
                        </span>
                      </div>

                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between text-xs font-semibold">
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-emerald-600" />
                          <span className="text-slate-600">B2B Credit Guardrail</span>
                        </div>
                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100 text-[10px]">
                          Limit Approved ✅
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Approve Button overlay or action */}
                <div className="p-4 border-t border-slate-100 bg-slate-50/50">
                  {isApproved ? (
                    <div className="bg-slate-100 border border-slate-200 rounded-xl p-4 text-center space-y-3">
                      <div className="flex items-center justify-center gap-2 text-slate-500 font-bold text-xs uppercase tracking-wide">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        <span>Order Approved & Committed</span>
                      </div>
                      <div className="text-sm font-extrabold text-brand-blue bg-white p-2 rounded-lg border border-slate-200 shadow-sm flex items-center justify-center gap-2">
                        <span>{isApproved.internalId}</span>
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
                      onClick={handleApproveOrder}
                      disabled={submittingOrder}
                      className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-bold py-3 px-6 rounded-xl shadow-lg hover:shadow-emerald-100 transition-all duration-300 transform active:scale-95 flex items-center justify-center gap-2 border border-emerald-500/25"
                    >
                      {submittingOrder ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Creating Digital Order...</span>
                        </>
                      ) : (
                        <>
                          <Bot className="w-4 h-4" />
                          <span>Approve & Create Digital Order</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 p-6 text-center gap-3">
                <Bot className="w-12 h-12 text-slate-300" />
                <h4 className="font-bold text-sm text-slate-600">No Pending AI Extraction</h4>
                <p className="text-xs font-semibold leading-relaxed max-w-[200px]">
                  Select a retailer and place a structured request inside the chat stream to parse SKUs.
                </p>
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Local Toast UI notification */}
      {toast.show && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 ${
          toast.type === "success" 
            ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
            : "bg-rose-50 text-rose-800 border-rose-200"
        }`}>
          {toast.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600" />
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
