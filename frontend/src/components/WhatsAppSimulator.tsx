"use client";

import React, { useState, useEffect } from "react";
import { MessageSquare, Send, User, Phone, Layers, Radio, Sparkles } from "lucide-react";

interface Customer {
  id: string;
  customer_id: string;
  retailer_name: string;
  phone_number: string;
  tenant_id: string;
}

interface WhatsAppSimulatorProps {
  activeTenantId: string;
  onSuccess?: () => void;
}

export default function WhatsAppSimulator({ activeTenantId, onSuccess }: WhatsAppSimulatorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isLoadingCustomers, setIsLoadingCustomers] = useState(false);
  
  // Simulation Inputs
  const [selectedCustomerId, setSelectedCustomerId] = useState("custom");
  const [customName, setCustomName] = useState("New Store Test");
  const [customPhone, setCustomPhone] = useState("+919999888877");
  const [messageText, setMessageText] = useState("Bhaiya, send 10 cases of Britannia Marie Gold and 5 cases of HUL Surf Excel immediately.");
  const [isSending, setIsSending] = useState(false);

  // Synchronize Live Registered Customers from Workspace Tenant
  useEffect(() => {
    if (!activeTenantId) return;

    const fetchWorkspaceCustomers = async () => {
      setIsLoadingCustomers(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const token = localStorage.getItem("accessToken");
        
        const response = await fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}`, {
          method: "GET",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
          }
        });

        if (response.ok) {
          const data = await response.json();
          // Adjust parsing logic based on endpoint array encapsulation structures
          setCustomers(Array.isArray(data) ? data : data.items || []);
        }
      } catch (err) {
        console.error("Failed to sync client workspace entities into simulator:", err);
      } finally {
        setIsLoadingCustomers(false);
      }
    };

    fetchWorkspaceCustomers();
  }, [activeTenantId]);

  // Adjust inputs when choosing a live whitelisted customer option
  const handleCustomerSelection = (id: string) => {
    setSelectedCustomerId(id);
    if (id === "custom") {
      setCustomName("Manual Operational Node");
      setCustomPhone("+91");
    } else {
      const match = customers.find((c) => c.id === id);
      if (match) {
        setCustomName(match.retailer_name);
        setCustomPhone(match.phone_number || "");
      }
    }
  };

  const handleFireWebhookSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customPhone || !messageText) return;

    setIsSending(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      
      const payload = {
        object: "whatsapp_business_account",
        entry: [
          {
            id: "WHATSAPP_BUSINESS_ACCOUNT_ID",
            changes: [
              {
                value: {
                  messaging_product: "whatsapp",
                  metadata: {
                    display_phone_number: "15555555555",
                    phone_number_id: "BUSINESS_PHONE_NUMBER_ID"
                  },
                  contacts: [
                    {
                      profile: { name: customName },
                      wa_id: customPhone.replace("+", "")
                    }
                  ],
                  messages: [
                    {
                      from: customPhone.replace("+", ""),
                      id: `wamid.HBgLOTE5OTk5ODg4ODc3FQIAERgSQjRDQzhCQzNDQzRFQzVGMDVCAA==`,
                      timestamp: Math.floor(Date.now() / 1000).toString(),
                      text: { body: messageText },
                      type: "text"
                    }
                  ]
                },
                field: "messages"
              }
            ]
          }
        ]
      };

      const response = await fetch(`${apiBase}/api/v1/whatsapp/webhook`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        setMessageText("");
        if (onSuccess) onSuccess();
      } else {
        console.error("Simulation Webhook endpoint rejected payload configurations.");
      }
    } catch (err) {
      console.error("Fatal operational connection issue mapping payload execution:", err);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end">
      {isOpen && (
        <div className="bg-white border border-slate-100 rounded-2xl shadow-2xl p-5 mb-3 w-96 animate-slide-up text-slate-700">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
            <h3 className="text-xs font-bold tracking-tight text-slate-800">WhatsApp Ingestion Pipeline Simulator</h3>
          </div>

          <form onSubmit={handleFireWebhookSimulation} className="mt-4 space-y-3.5">
            {/* Whitelisted Customer Dynamic Picker Context */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Target Ingest Profile</label>
              <select
                value={selectedCustomerId}
                onChange={(e) => handleCustomerSelection(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-500 transition-all cursor-pointer"
              >
                <option value="custom">✨ Setup Custom Input Number Override...</option>
                {isLoadingCustomers ? (
                  <option disabled>Loading live whitelisted customers...</option>
                ) : customers.length === 0 ? (
                  <option disabled>No customers synced to active tenant</option>
                ) : (
                  customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      👤 {customer.retailer_name} ({customer.phone_number || "No Phone Key"})
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Custom Attributes Configuration Fields */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1">
                  <User className="w-3 h-3" /> Sender Name
                </label>
                <input
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  disabled={selectedCustomerId !== "custom"}
                  className="w-full bg-slate-50/50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-600 disabled:opacity-60 disabled:cursor-not-allowed outline-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1">
                  <Phone className="w-3 h-3" /> Phone Number
                </label>
                <input
                  type="text"
                  value={customPhone}
                  onChange={(e) => setCustomPhone(e.target.value)}
                  disabled={selectedCustomerId !== "custom"}
                  className="w-full bg-slate-50/50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-600 disabled:opacity-60 disabled:cursor-not-allowed outline-none"
                  placeholder="+91"
                />
              </div>
            </div>

            {/* Simulated Order Text Area */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Order Content Payload</label>
              <textarea
                rows={3}
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                placeholder="Type unstructured order copy text logs..."
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs font-medium text-slate-600 outline-none focus:border-emerald-500 transition-all resize-none leading-relaxed"
              />
            </div>

            {/* Execution Dispatch Anchor */}
            <button
              type="submit"
              disabled={isSending || !customPhone || !messageText}
              className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isSending ? "Processing AI Extraction..." : "Dispatch Ingestion Mock"}</span>
            </button>
          </form>
        </div>
      )}

      {/* Floating Toggle Button Core Wrapper */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-emerald-600 hover:bg-emerald-500 text-white rounded-full p-3.5 shadow-2xl flex items-center justify-center transition-all hover:scale-105 active:scale-95"
        title="Open WhatsApp Pipeline Simulator"
      >
        <MessageSquare className="w-5 h-5" />
      </button>
    </div>
  );
}
