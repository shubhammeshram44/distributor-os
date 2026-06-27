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

  // Evolution API provisioning states
  const [instanceName, setInstanceName] = useState("");
  const [provisioningStatus, setProvisioningStatus] = useState<"idle" | "provisioning" | "connecting" | "connected" | "error">("idle");
  const [qrCodeBase64, setQrCodeBase64] = useState("");
  const [evolutionError, setEvolutionError] = useState("");



  // Connection status polling
  useEffect(() => {
    if (provisioningStatus !== "connecting" || !instanceName) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    
    const checkStatus = async () => {
      try {
        const resp = await fetch(`${apiBase}/api/v1/evolution/status?instance_name=${instanceName}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.status === "open") {
            setProvisioningStatus("connected");
            showToast("WhatsApp Instance successfully connected!", "success");
          }
        }
      } catch (err) {
        console.error("Error polling connection status:", err);
      }
    };

    const interval = setInterval(checkStatus, 3000);
    return () => clearInterval(interval);
  }, [provisioningStatus, instanceName]);

  const handleProvisionEvolution = async (e: React.FormEvent) => {
    e.preventDefault();

    setProvisioningStatus("provisioning");
    setEvolutionError("");
    setQrCodeBase64("");

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/evolution/provision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });

      const data = await resp.json();

      if (resp.ok && data.status === "success") {
        if (data.instance_name) {
          setInstanceName(data.instance_name);
        }
        if (data.connection_status === "open") {
          setProvisioningStatus("connected");
          showToast("WhatsApp Instance is already open and connected!", "success");
        } else if (data.qr_code) {
          setQrCodeBase64(data.qr_code);
          setProvisioningStatus("connecting");
          showToast("QR code generated! Scan with your WhatsApp app.", "success");
        } else {
          setProvisioningStatus("connecting");
          showToast("Instance provisioned, waiting for QR stream...", "success");
        }
      } else {
        setProvisioningStatus("error");
        setEvolutionError(data.detail || "Failed to provision Evolution API instance.");
        showToast(data.detail || "Failed to provision WhatsApp instance.", "error");
      }
    } catch (err) {
      console.error("Provisioning failed:", err);
      setProvisioningStatus("error");
      setEvolutionError("Network connection failure during provisioning request.");
      showToast("Network connection error.", "error");
    }
  };
  
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
          if (data.whatsapp_phone_id) {
            setInstanceName(data.whatsapp_phone_id);
            setProvisioningStatus("connected");
          }
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
              {/* // LEGACY_META_CODE_START */}
              {/* 
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
              */}
              {/* // LEGACY_META_CODE_END */}

              {/* Evolution API Connection & Provisioning */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mt-6">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                      EV
                    </div>
                    <div>
                      <h3 className="font-extrabold text-slate-800 text-base">Evolution API Integration</h3>
                      <p className="text-xs text-slate-400 font-semibold mt-0.5">
                        Scan QR code to connect and provision a new WhatsApp instance.
                      </p>
                    </div>
                  </div>
                  <div>
                    {provisioningStatus === "connected" ? (
                      <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>Connected</span>
                      </span>
                    ) : provisioningStatus === "connecting" ? (
                      <span className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 border border-amber-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm animate-pulse">
                        <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                        <span>Connecting (Scan QR)</span>
                      </span>
                    ) : provisioningStatus === "provisioning" ? (
                      <span className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm animate-pulse">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                        <span>Provisioning...</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 bg-slate-50 text-slate-500 border border-slate-200 px-3 py-1 rounded-full text-xs font-bold">
                        <Lock className="w-4 h-4 text-slate-400" />
                        <span>Not Connected</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-4 flex gap-3 text-slate-600 text-xs leading-relaxed font-semibold">
                    <AlertCircle className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="text-slate-800 font-bold">Evolution API Connection Instructions:</span>
                      <ul className="list-disc pl-4 mt-1.5 space-y-1 text-slate-500 font-medium">
                        <li>Click "Connect WhatsApp" to initialize the connection.</li>
                        <li>The system will auto-generate a unique instance ID for your workspace.</li>
                        <li>Scan the generated QR code using the "Link a Device" option in your WhatsApp app.</li>
                        <li>The system will automatically detect the connection and activate the ingestion pipeline.</li>
                      </ul>
                    </div>
                  </div>

                  <form onSubmit={handleProvisionEvolution} className="space-y-5">

                    {qrCodeBase64 && (provisioningStatus === "connecting" || provisioningStatus === "provisioning") && (
                      <div className="flex flex-col items-center justify-center p-6 bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-4">
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Scan this QR code with WhatsApp</p>
                        <div className="bg-white p-4 rounded-xl shadow-md border border-slate-100">
                          <img src={qrCodeBase64} alt="WhatsApp QR Code" className="w-48 h-48" />
                        </div>
                        <p className="text-[10px] text-slate-400 font-semibold animate-pulse flex items-center gap-1.5">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Waiting for scan authorization...</span>
                        </p>
                      </div>
                    )}

                    {evolutionError && (
                      <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>{evolutionError}</span>
                      </div>
                    )}

                    <div className="flex justify-end pt-2 border-t border-slate-100 mt-6">
                      <button
                        type="submit"
                        disabled={provisioningStatus === "provisioning" || provisioningStatus === "connecting"}
                        className="px-6 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-emerald-700 disabled:opacity-55 flex items-center gap-2 cursor-pointer transition-all"
                      >
                        {provisioningStatus === "provisioning" ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Connecting...</span>
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
