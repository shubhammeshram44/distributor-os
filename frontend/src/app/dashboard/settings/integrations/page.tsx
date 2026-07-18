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
  Lock,
  XCircle
} from "lucide-react";

export default function IntegrationsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [whatsappPhoneId, setWhatsappPhoneId] = useState("");
  const [whatsappAccessToken, setWhatsappAccessToken] = useState("");
  const [whatsappOrderPhone, setWhatsappOrderPhone] = useState("");
  const [ownerJid, setOwnerJid] = useState("");
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  
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

  // Business profile (GSTIN) state
  const [businessGstin, setBusinessGstin] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [businessCategory, setBusinessCategory] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);



  // Connection status polling
  useEffect(() => {
    if (provisioningStatus !== "connecting" || !instanceName) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    
    const checkStatus = async () => {
      try {
        const resp = await fetch(`${apiBase}/api/v1/evolution/status?instance_name=${instanceName}&tenant_id=${activeTenantId}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.status === "open") {
            setProvisioningStatus("connected");
            if (data.ownerJid) {
              setOwnerJid(data.ownerJid);
            }
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
      const resp = await fetch(`${apiBase}/api/v1/evolution/provision?tenant_id=${activeTenantId}`, {
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
          setWhatsappOrderPhone(data.whatsapp_order_phone || "");
          if (data.whatsapp_phone_id) {
            setInstanceName(data.whatsapp_phone_id);
            // Verify connection status
            try {
              const statusResp = await fetch(`${apiBase}/api/v1/evolution/status?instance_name=${data.whatsapp_phone_id}`);
              if (statusResp.ok) {
                const statusData = await statusResp.json();
                if (statusData.status === "open") {
                  setProvisioningStatus("connected");
                  if (statusData.ownerJid) {
                    setOwnerJid(statusData.ownerJid);
                  }
                } else {
                  setProvisioningStatus("idle");
                }
              } else {
                setProvisioningStatus("idle");
              }
            } catch (err) {
              console.error("Error fetching connection status on mount:", err);
              setProvisioningStatus("idle");
            }
          } else {
            setProvisioningStatus("idle");
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

  // Fetch tenant business profile (name, category, GSTIN)
  useEffect(() => {
    if (!activeTenantId) return;

    const fetchProfile = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${apiBase}/api/v1/tenant/profile?tenant_id=${activeTenantId}`, {
          credentials: "include"
        });
        if (resp.ok) {
          const data = await resp.json();
          setBusinessName(data.tenant?.name || "");
          setBusinessCategory(data.tenant?.category || "");
          setBusinessGstin(data.tenant?.gstin || "");
        }
      } catch (err) {
        console.error("Failed to load business profile:", err);
      }
    };

    fetchProfile();
  }, [activeTenantId]);

  const handleSaveBusinessProfile = async () => {
    const trimmedGstin = businessGstin.trim().toUpperCase();
    if (trimmedGstin && !/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(trimmedGstin)) {
      showToast("That doesn't look like a valid 15-character GSTIN.", "error");
      return;
    }

    setSavingProfile(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-Tenant-ID": activeTenantId },
        body: JSON.stringify({
          name: businessName.trim() || "Untitled Business",
          category: businessCategory.trim() || "FMCG",
          gstin: trimmedGstin || null,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "Failed to update business profile.");
      }
      setBusinessGstin(data.tenant?.gstin || "");
      showToast("Business profile updated successfully.", "success");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to update business profile.";
      showToast(message, "error");
    } finally {
      setSavingProfile(false);
    }
  };

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

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/evolution/disconnect?instance_name=${instanceName}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (resp.ok) {
        showToast("WhatsApp disconnected successfully.", "success");
        setProvisioningStatus("idle");
        setInstanceName("");
        setOwnerJid("");
        setWhatsappOrderPhone("");
        setWhatsappPhoneId("");
        setQrCodeBase64("");
      } else {
        const data = await resp.json();
        showToast(data.detail || "Failed to disconnect WhatsApp.", "error");
      }
    } catch (err) {
      console.error("Disconnect failed:", err);
      showToast("Network error during disconnect request.", "error");
    } finally {
      setDisconnecting(false);
      setShowDisconnectModal(false);
    }
  };

  const isConnected = whatsappPhoneId && whatsappAccessToken;
  const displayPhone = ownerJid ? ownerJid.replace("@s.whatsapp.net", "") : whatsappOrderPhone;

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
              {/* Business Profile / GSTIN — required for a legally correct Tax Invoice */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100">
                  <h3 className="font-extrabold text-slate-800 text-base">Business Profile</h3>
                  <p className="text-xs text-slate-400 font-semibold mt-0.5">
                    Shown on your customers&apos; Tax Invoices.
                  </p>
                </div>
                <div className="p-6 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider">
                        Business Name
                      </label>
                      <input
                        type="text"
                        value={businessName}
                        onChange={(e) => setBusinessName(e.target.value)}
                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-slate-50/20 text-slate-700"
                        disabled={savingProfile}
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider">
                        GSTIN <span className="normal-case font-medium text-slate-400">(optional)</span>
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. 29AAAAA1111A1Z1"
                        value={businessGstin}
                        onChange={(e) => setBusinessGstin(e.target.value.toUpperCase())}
                        maxLength={15}
                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-slate-50/20 text-slate-700 uppercase"
                        disabled={savingProfile}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end pt-2 border-t border-slate-100 mt-2">
                    <button
                      type="button"
                      onClick={handleSaveBusinessProfile}
                      disabled={savingProfile}
                      className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer"
                    >
                      {savingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                      <span>Save Business Profile</span>
                    </button>
                  </div>
                </div>
              </div>

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
                      <span className="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 border border-rose-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                        <XCircle className="w-4 h-4 text-rose-600" />
                        <span>Not Connected</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {provisioningStatus === "connected" ? (
                    <div className="space-y-4">
                      <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-4 flex flex-col gap-2">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Connected Phone Number</span>
                          <span className="text-sm font-bold text-slate-800">
                            +{displayPhone.replace("+", "")}
                          </span>
                        </div>
                        <div className="flex justify-between items-center border-t border-slate-200/60 pt-2 mt-1">
                          <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Instance ID</span>
                          <span className="text-xs font-semibold text-slate-500 font-mono">
                            {instanceName}
                          </span>
                        </div>
                      </div>

                      <div className="flex justify-end pt-2 border-t border-slate-100 mt-6">
                        <button
                          type="button"
                          onClick={() => setShowDisconnectModal(true)}
                          className="px-6 py-2.5 bg-rose-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-rose-700 cursor-pointer transition-all animate-in fade-in duration-200"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
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
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {showDisconnectModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-slate-100 p-6 space-y-6 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-50 rounded-full text-rose-600">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-950">Disconnect WhatsApp</h3>
                <p className="text-sm text-slate-500 font-medium leading-relaxed font-semibold">
                  This will disconnect your WhatsApp. New orders will stop coming in. Are you sure?
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={disconnecting}
                onClick={() => setShowDisconnectModal(false)}
                className="px-4 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-bold cursor-pointer transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={disconnecting}
                onClick={handleDisconnect}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-bold shadow-md disabled:opacity-55 flex items-center gap-1.5 cursor-pointer transition-all"
              >
                {disconnecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Disconnecting...</span>
                  </>
                ) : (
                  <span>Yes, Disconnect</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

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
