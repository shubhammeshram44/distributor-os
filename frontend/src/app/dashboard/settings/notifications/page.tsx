"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  Bell,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Save,
  MessageSquareCode
} from "lucide-react";

interface NotificationPrefs {
  order_received: boolean;
  order_confirmed: boolean;
  order_dispatched: boolean;
  order_delivered: boolean;
  payment_reminder: boolean;
  new_order_alert_to_distributor: boolean;
}

const PREF_LABELS = {
  order_received: {
    title: "Order Received Confirmation",
    desc: "Send an automated confirmation message to customers when their order is captured via WhatsApp."
  },
  order_confirmed: {
    title: "Order Confirmed Alert",
    desc: "Alert customers immediately when their order status changes to Confirmed."
  },
  order_dispatched: {
    title: "Order Dispatched Alert",
    desc: "Notify customers when their order has been dispatched from the warehouse."
  },
  order_delivered: {
    title: "Order Delivered Alert",
    desc: "Notify customers when their order has been successfully delivered."
  },
  payment_reminder: {
    title: "Payment Reminder",
    desc: "Send payment notifications or reminders to customers with outstanding balances."
  },
  new_order_alert_to_distributor: {
    title: "New Order Alert (to you)",
    desc: "Receive a WhatsApp ping on your own registered phone number when a new order is received."
  }
};

export default function NotificationsSettingsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPrefs>({
    order_received: true,
    order_confirmed: true,
    order_dispatched: true,
    order_delivered: true,
    payment_reminder: true,
    new_order_alert_to_distributor: true
  });

  const [toast, setToast] = useState({ show: false, message: "", type: "success" as "success" | "error" });

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
    } else {
      setLoading(false);
    }
  }, []);

  // Fetch notification preferences when activeTenantId resolves
  useEffect(() => {
    if (!activeTenantId) return;

    const fetchPrefs = async () => {
      setLoading(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${apiBase}/api/v1/tenant/notification-prefs?tenant_id=${activeTenantId}`, {
          credentials: "include"
        });

        if (resp.ok) {
          const data = await resp.json();
          // Ensure all fields are present
          setPrefs({
            order_received: data.order_received !== false,
            order_confirmed: data.order_confirmed !== false,
            order_dispatched: data.order_dispatched !== false,
            order_delivered: data.order_delivered !== false,
            payment_reminder: data.payment_reminder !== false,
            new_order_alert_to_distributor: data.new_order_alert_to_distributor !== false
          });
        } else {
          showToast("Failed to fetch notification preferences.", "error");
        }
      } catch (err) {
        console.error("Failed to load notification preferences:", err);
        showToast("Error loading preferences from server.", "error");
      } finally {
        setLoading(false);
      }
    };

    fetchPrefs();
  }, [activeTenantId]);

  const handleToggle = async (key: keyof NotificationPrefs) => {
    const updatedValue = !prefs[key];
    
    // Optimistic UI update
    setPrefs(prev => ({
      ...prev,
      [key]: updatedValue
    }));

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/notification-prefs?tenant_id=${activeTenantId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          [key]: updatedValue
        })
      });

      if (resp.ok) {
        showToast("Preferences updated successfully!", "success");
      } else {
        // Rollback state on error
        setPrefs(prev => ({
          ...prev,
          [key]: !updatedValue
        }));
        const data = await resp.json();
        showToast(data.detail || "Failed to update notification preference.", "error");
      }
    } catch (err) {
      console.error("Failed to save preference:", err);
      // Rollback state on error
      setPrefs(prev => ({
        ...prev,
        [key]: !updatedValue
      }));
      showToast("Connection error updating preferences.", "error");
    }
  };

  const getTenantName = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("tenant_name") || "My Workspace";
    }
    return "My Workspace";
  };

  const handleTenantChange = (id: string) => {
    setActiveTenantId(id);
    localStorage.setItem("tenant_id", id);
  };

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800 font-sans">
      {/* Sidebar */}
      <Sidebar
        activeTab="Notifications"
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
          {/* Toast Notification */}
          {toast.show && (
            <div className={`fixed top-20 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-md border transition-all duration-300 ${
              toast.type === "success" 
                ? "bg-emerald-50 border-emerald-200 text-emerald-800" 
                : "bg-rose-50 border-rose-200 text-rose-800"
            }`}>
              {toast.type === "success" ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <AlertCircle className="w-5 h-5 text-rose-600" />}
              <span className="text-sm font-semibold">{toast.message}</span>
            </div>
          )}

          <div className="p-8 max-w-4xl mx-auto space-y-6">
            {/* Header Card */}
            <div className="bg-white border border-dashboard-border rounded-xl p-6 shadow-sm flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
                  <Bell className="w-6 h-6 text-brand-blue" />
                  WhatsApp Notifications
                </h2>
                <p className="text-slate-500 text-sm mt-1">
                  Configure automated WhatsApp notifications triggered by key order lifecycle events.
                </p>
              </div>
              <span className="px-3 py-1 bg-brand-blue/10 text-brand-blue border border-brand-blue/20 text-xs font-semibold rounded-full uppercase tracking-wider">
                {getTenantName()}
              </span>
            </div>

            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <Loader2 className="w-10 h-10 text-brand-blue animate-spin" />
                <span className="text-slate-500 text-sm font-medium animate-pulse">Loading notification preferences...</span>
              </div>
            ) : (
              <div className="bg-white border border-dashboard-border rounded-xl overflow-hidden shadow-sm">
                <div className="px-6 py-4 border-b border-dashboard-border bg-slate-50 flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Notification Preferences</span>
                  <span className="text-xs text-slate-400 font-medium">Auto-saves on change</span>
                </div>
                <div className="divide-y divide-dashboard-border">
                  {(Object.keys(PREF_LABELS) as Array<keyof NotificationPrefs>).map((key) => {
                    const label = PREF_LABELS[key];
                    const isChecked = prefs[key];
                    return (
                      <div key={key} className="px-6 py-5 flex items-center justify-between hover:bg-slate-50/50 transition-all duration-200">
                        <div className="space-y-1 pr-6">
                          <h4 className="text-sm font-semibold text-slate-800">{label.title}</h4>
                          <p className="text-xs text-slate-500 leading-relaxed max-w-xl">{label.desc}</p>
                        </div>
                        
                        {/* Toggle Switch */}
                        <button
                          onClick={() => handleToggle(key)}
                          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                            isChecked ? "bg-emerald-500" : "bg-slate-200"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              isChecked ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Template Info Card */}
            <div className="bg-slate-50 border border-dashboard-border rounded-xl p-5 flex gap-4">
              <MessageSquareCode className="w-8 h-8 text-slate-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h5 className="text-xs font-bold uppercase text-slate-500 tracking-wider">Templated Messaging</h5>
                <p className="text-xs text-slate-400 leading-relaxed">
                  All alerts use pre-formatted country-code validated templates to optimize delivery success. Ensure your WhatsApp instance is correctly connected via the <a href="/dashboard/settings/integrations" className="text-brand-blue hover:underline">Integrations</a> page.
                </p>
              </div>
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}
