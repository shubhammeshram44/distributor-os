"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  Smartphone,
  Key,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Link2,
  Loader2,
  Lock
} from "lucide-react";

export default function IntegrationsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [whatsappPhoneId, setWhatsappPhoneId] = useState("");
  const [whatsappAccessToken, setWhatsappAccessToken] = useState("");
  
  // Masked visibility states
  const [showPhoneId, setShowPhoneId] = useState(false);
  const [showToken, setShowToken] = useState(false);
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
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

  // Sync tenant from localStorage on load
  useEffect(() => {
    const stored = localStorage.getItem("tenant_id");
    if (stored) {
      setActiveTenantId(stored);
    } else {
      setLoading(false);
    }
  }, []);

  // Fetch integration settings from backend when activeTenantId resolves
  useEffect(() => {
    if (!activeTenantId) return;

    const fetchSettings = async () => {
      setLoading(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${apiBase}/api/v1/tenant/integrations/whatsapp?tenant_id=${activeTenantId}`, {
          credentials: "include"
        });
        if (resp.ok) {
          const data = await resp.json();
          setWhatsappPhoneId(data.whatsapp_phone_id || "");
          setWhatsappAccessToken(data.whatsapp_access_token || "");
        } else {
          showToast("Failed to fetch WhatsApp integration details.", "error");
        }
      } catch (err) {
        console.error("Failed to load integrations:", err);
        showToast("Error loading integrations from server.", "error");
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [activeTenantId]);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!whatsappPhoneId.trim() || !whatsappAccessToken.trim()) {
      showToast("Both Phone Number ID and Access Token are required.", "error");
      return;
    }

    setSaving(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/integrations/whatsapp?tenant_id=${activeTenantId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          whatsapp_phone_id: whatsappPhoneId.trim(),
          whatsapp_access_token: whatsappAccessToken.trim()
        })
      });

      if (resp.ok) {
        showToast("WhatsApp configuration saved successfully!", "success");
        // Reload details to get masked version of token if updated
        const getResp = await fetch(`${apiBase}/api/v1/tenant/integrations/whatsapp?tenant_id=${activeTenantId}`, {
          credentials: "include"
        });
        if (getResp.ok) {
          const getData = await getResp.json();
          setWhatsappPhoneId(getData.whatsapp_phone_id || "");
          setWhatsappAccessToken(getData.whatsapp_access_token || "");
        }
      } else {
        const data = await resp.json();
        showToast(data.detail || "Failed to update WhatsApp configuration.", "error");
      }
    } catch (err) {
      console.error("Save config failed:", err);
      showToast("An unexpected connection error occurred.", "error");
    } finally {
      setSaving(false);
    }
  };

  const isConnected = whatsappPhoneId && whatsappAccessToken;

  return (
    <div className="flex h-screen bg-[#F8FAFC]">
      <Sidebar activeTab="Integrations" setActiveTab={() => {}} tenantName={getTenantName()} />
      
      <div className="flex-1 flex flex-col md:pl-64 min-h-screen">
        <DashboardHeader onTenantChange={handleTenantChange} />
        
        <main className="flex-1 p-6 space-y-6 max-w-4xl w-full mx-auto">

          <div>
            <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
              <Link2 className="w-5 h-5 text-brand-blue" />
              <span>Integrations & Connections</span>
            </h1>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              Connect external services, configure webhooks, and manage APIs.
            </p>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <Loader2 className="w-10 h-10 text-brand-blue animate-spin" />
              <p className="text-sm font-semibold text-slate-400">Loading configurations...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* WhatsApp Config Card */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                      <Link2 className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-extrabold text-slate-800 text-base">WhatsApp Business API</h3>
                      <p className="text-xs text-slate-400 font-semibold mt-0.5">
                        Direct multi-tenant conversational webhook routing channel.
                      </p>
                    </div>
                  </div>
                  <div>
                    {isConnected ? (
                      <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>Connected</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 bg-slate-50 text-slate-500 border border-slate-200 px-3 py-1 rounded-full text-xs font-bold">
                        <Lock className="w-4 h-4 text-slate-400" />
                        <span>Not Configured</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-4 flex gap-3 text-slate-600 text-xs leading-relaxed font-semibold">
                    <AlertCircle className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="text-slate-800 font-bold">Configuration Instructions:</span>
                      <ul className="list-disc pl-4 mt-1.5 space-y-1 text-slate-500 font-medium">
                        <li>Retrieve your <span className="font-semibold text-slate-700">Phone Number ID</span> from your Meta Developer Portal under WhatsApp &gt; API Setup.</li>
                        <li>Generate a <span className="font-semibold text-slate-700">Permanent Access Token</span> from your Meta Business Suite System User Settings.</li>
                        <li>Incoming webhooks will resolve this tenant ID using the configured Phone Number ID.</li>
                      </ul>
                    </div>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      {/* Phone ID */}
                      <div className="relative">
                        <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wide">
                          WhatsApp Phone Number ID *
                        </label>
                        <div className="relative rounded-lg shadow-sm">
                          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Smartphone className="h-4 w-4 text-slate-400" />
                          </div>
                          <input
                            type={showPhoneId ? "text" : "password"}
                            value={whatsappPhoneId}
                            onChange={(e) => setWhatsappPhoneId(e.target.value)}
                            required
                            placeholder="e.g. 104928184719047"
                            className="w-full pl-10 pr-10 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPhoneId(!showPhoneId)}
                            className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                          >
                            {showPhoneId ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>

                      {/* Access Token */}
                      <div className="relative">
                        <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wide">
                          Permanent Access Token *
                        </label>
                        <div className="relative rounded-lg shadow-sm">
                          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Key className="h-4 w-4 text-slate-400" />
                          </div>
                          <input
                            type={showToken ? "text" : "password"}
                            value={whatsappAccessToken}
                            onChange={(e) => setWhatsappAccessToken(e.target.value)}
                            required
                            placeholder="EAAGxxxxxxxxxxxxxxxxxxxx"
                            className="w-full pl-10 pr-10 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                          />
                          <button
                            type="button"
                            onClick={() => setShowToken(!showToken)}
                            className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                          >
                            {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end pt-2 border-t border-slate-100 mt-6">
                      <button
                        type="submit"
                        disabled={saving}
                        className="px-6 py-2.5 bg-brand-blue text-white rounded-lg text-sm font-bold shadow-md hover:bg-brand-blueHover disabled:opacity-50 flex items-center gap-2 cursor-pointer transition-all"
                      >
                        {saving ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Saving Changes...</span>
                          </>
                        ) : (
                          <span>Connect WhatsApp</span>
                        )}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Elegant Toast Notifications */}
      {toast.show && (
        <div className="fixed bottom-5 right-5 z-50 animate-slide-in">
          <div className={`flex items-center gap-3 px-5 py-3 rounded-lg border shadow-xl bg-white ${
            toast.type === "success" 
              ? "border-emerald-200 text-emerald-800" 
              : "border-rose-200 text-rose-800"
          }`}>
            <span className="text-lg">
              {toast.type === "success" ? "✓" : "⚠"}
            </span>
            <span className="text-xs font-bold tracking-wide">
              {toast.message}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
