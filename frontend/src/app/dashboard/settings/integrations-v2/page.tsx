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
  XCircle,
  CreditCard,
  ExternalLink,
  ShieldCheck
} from "lucide-react";

export default function IntegrationsPageV2() {
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
  const [provisioningStatus, setProvisioningStatus] = useState<"idle" | "provisioning" | "connecting" | "connected" | "disconnected" | "error">("idle");
  const [qrCodeBase64, setQrCodeBase64] = useState("");
  const [evolutionError, setEvolutionError] = useState("");

  // Business profile (GSTIN) state
  const [businessGstin, setBusinessGstin] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [businessCategory, setBusinessCategory] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Integrations V2 UI states
  const [activeTab, setActiveTab] = useState("All");
  const [whatsappExpanded, setWhatsappExpanded] = useState(false);
  const [razorpayExpanded, setRazorpayExpanded] = useState(false);
  const [integrationRequest, setIntegrationRequest] = useState("");

  // Razorpay states
  const [razorpayConnected, setRazorpayConnected] = useState(false);
  const [keyIdMasked, setKeyIdMasked] = useState("");
  const [accountName, setAccountName] = useState("");
  const [razorpayMode, setRazorpayMode] = useState("test");

  // Razorpay form states
  const [keyIdInput, setKeyIdInput] = useState("");
  const [keySecretInput, setKeySecretInput] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [showUpdateForm, setShowUpdateForm] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [disconnectingRazorpay, setDisconnectingRazorpay] = useState(false);
  const [showRazorpayDisconnectModal, setShowRazorpayDisconnectModal] = useState(false);

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

        // Intercept for active open state or backend "ALREADY_CONNECTED" string
        if (data.connection_status === "open" || data.qr_code === "ALREADY_CONNECTED") {
          setProvisioningStatus("connected");
          setQrCodeBase64(""); // Flush out any stale QR text strings
          showToast("WhatsApp Instance is already open and connected!", "success");
        } else if (data.qr_code) {
          // Guard against raw non-base64 strings and structure the base64 URL properly
          setQrCodeBase64(data.qr_code.startsWith("data:") ? data.qr_code : `data:image/png;base64,${data.qr_code}`);
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
            const statusResp = await fetch(
              `${apiBase}/api/v1/evolution/status?instance_name=${data.whatsapp_phone_id}&tenant_id=${activeTenantId}`
            );
            if (statusResp.ok) {
              const statusData = await statusResp.json();
              if (statusData.connected === true || statusData.status === "open") {
                setProvisioningStatus("connected");
                if (statusData.owner_phone) {
                  setWhatsappOrderPhone(statusData.owner_phone);
                }
              } else {
                // Was previously connected (phone_id exists) but now disconnected
                setProvisioningStatus("disconnected");
              }
            } else {
              // API call failed — assume disconnected if phone_id existed
              setProvisioningStatus("disconnected");
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

  // Fetch Razorpay connection status
  const fetchRazorpayStatus = async () => {
    if (!activeTenantId) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/razorpay-status?tenant_id=${activeTenantId}`, {
        credentials: "include"
      });
      if (resp.ok) {
        const data = await resp.json();
        setRazorpayConnected(data.connected);
        setKeyIdMasked(data.key_id_masked || "");
        setAccountName(data.account_name || "");
        setRazorpayMode(data.mode || "test");
      } else {
        showToast("Failed to fetch Razorpay connection status.", "error");
      }
    } catch (err) {
      console.error("Failed to load Razorpay status:", err);
      showToast("Error loading Razorpay configuration from server.", "error");
    }
  };

  useEffect(() => {
    fetchRazorpayStatus();
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

  const handleRazorpayConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyIdInput.trim() || !keySecretInput.trim()) {
      setValidationError("Both Key ID and Key Secret are required.");
      return;
    }

    setSaving(true);
    setValidationError("");
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/razorpay-connect?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key_id: keyIdInput.trim(),
          key_secret: keySecretInput.trim()
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        setRazorpayConnected(true);
        setKeyIdMasked(data.key_id_masked || "");
        setAccountName(data.account_name || "");
        setRazorpayMode(data.mode || "test");
        setKeyIdInput("");
        setKeySecretInput("");
        setShowUpdateForm(false);
        showToast("Razorpay account connected successfully!", "success");
      } else {
        setValidationError(data.detail || "Invalid Razorpay credentials");
        showToast(data.detail || "Connection failed.", "error");
      }
    } catch (err) {
      console.error("Connect failed:", err);
      setValidationError("Network connection failure during request.");
      showToast("Network connection error.", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleRazorpayDisconnect = async () => {
    setDisconnectingRazorpay(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/razorpay-disconnect?tenant_id=${activeTenantId}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (resp.ok) {
        setRazorpayConnected(false);
        setKeyIdMasked("");
        setAccountName("");
        setRazorpayMode("test");
        showToast("Razorpay account disconnected.", "success");
      } else {
        const data = await resp.json();
        showToast(data.detail || "Failed to disconnect Razorpay.", "error");
      }
    } catch (err) {
      console.error("Disconnect failed:", err);
      showToast("Network error during disconnect request.", "error");
    } finally {
      setDisconnectingRazorpay(false);
      setShowRazorpayDisconnectModal(false);
    }
  };

  const displayPhone = ownerJid ? ownerJid.replace("@s.whatsapp.net", "") : whatsappOrderPhone;

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-dashboard-inset">
      <Sidebar activeTab="Integrations" setActiveTab={() => {}} tenantName={getTenantName()} />
      
      <main className="flex-1 md:pl-64 min-h-screen flex flex-col">
        <DashboardHeader onTenantChange={handleTenantChange} />
        
        {loading ? (
          <div className="flex flex-col items-center justify-center flex-1 py-20 space-y-4">
            <Loader2 className="w-10 h-10 text-emerald-600 dark:text-emerald-400 animate-spin" />
            <p className="text-sm font-semibold text-slate-400">Loading configurations...</p>
          </div>
        ) : (
          <div className="p-8 max-w-5xl w-full mx-auto space-y-8">
            
            {/* Page header */}
            <div className="mb-4">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Integrations</h1>
              <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                Connect your tools to automate your distribution business.
              </p>
            </div>

            {/* Business Profile / GSTIN */}
            <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-6">
              <div>
                <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Business Profile</h3>
                <p className="text-xs text-slate-400 font-semibold mt-0.5">
                  Shown on your customers&apos; Tax Invoices.
                </p>
              </div>
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
                      Business Name
                    </label>
                    <input
                      type="text"
                      value={businessName}
                      onChange={(e) => setBusinessName(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 dark:border-white/10 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 bg-slate-50/20 dark:bg-white/5 text-slate-700 dark:text-slate-300"
                      disabled={savingProfile}
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
                      GSTIN <span className="normal-case font-medium text-slate-400">(optional)</span>
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. 29AAAAA1111A1Z1"
                      value={businessGstin}
                      onChange={(e) => setBusinessGstin(e.target.value.toUpperCase())}
                      maxLength={15}
                      className="w-full px-4 py-2 border border-slate-200 dark:border-white/10 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 bg-slate-50/20 dark:bg-white/5 text-slate-700 dark:text-slate-300 uppercase"
                      disabled={savingProfile}
                    />
                  </div>
                </div>
                <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-white/5 mt-2">
                  <button
                    type="button"
                    onClick={handleSaveBusinessProfile}
                    disabled={savingProfile}
                    className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer"
                  >
                    {savingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Save Business Profile</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Category tabs */}
            <div className="flex gap-2 mb-4 border-b border-slate-200 dark:border-white/10">
              {["All", "Communication", "Payments"].map(tab => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
                      : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Connected integrations */}
            <div>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Connected
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                {/* WhatsApp Card */}
                {(activeTab === "All" || activeTab === "Communication") && (
                  <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-green-50 dark:bg-green-500/10 rounded-xl flex items-center justify-center text-xl">
                          💬
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">WhatsApp</h3>
                          <p className="text-xs text-slate-400">Order intake & notifications</p>
                        </div>
                      </div>
                       {provisioningStatus === "connected" ? (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          Connected
                        </span>
                      ) : provisioningStatus === "disconnected" ? (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-500/10 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                          Disconnected
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/5 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          Not Connected
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                      Retailers order via WhatsApp as usual. Orders appear in your dashboard automatically.
                    </p>
                    
                    {/* Expand/collapse toggle */}
                    <button
                      type="button"
                      onClick={() => setWhatsappExpanded(!whatsappExpanded)}
                      className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 cursor-pointer"
                    >
                      {whatsappExpanded ? "Hide details ▲" : (whatsappPhoneId ? "Manage →" : "Connect →")}
                    </button>

                    {/* Existing WhatsApp connect/disconnect/QR JSX — show when expanded */}
                    {whatsappExpanded && (
                      <div className="mt-4 pt-4 border-t border-slate-100 dark:border-white/5">
                        {provisioningStatus === "connected" ? (
                          <div className="space-y-4">
                            <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-4 flex flex-col gap-2">
                              <div className="flex justify-between items-center">
                                <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Connected Phone Number</span>
                                <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                                  +{displayPhone.replace("+", "")}
                                </span>
                              </div>
                              <div className="flex justify-between items-center border-t border-slate-200/60 dark:border-white/[0.08] pt-2 mt-1">
                                <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Instance ID</span>
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-mono">
                                  {instanceName}
                                </span>
                              </div>
                            </div>

                            <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-white/5 mt-6">
                              <button
                                type="button"
                                onClick={() => setShowDisconnectModal(true)}
                                className="px-6 py-2.5 bg-rose-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-rose-700 cursor-pointer transition-all animate-in fade-in duration-200"
                              >
                                Disconnect
                              </button>
                            </div>
                          </div>
                        ) : provisioningStatus === "disconnected" ? (
                          <div className="space-y-4">
                            <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl p-5">
                              <div className="flex items-start gap-3">
                                <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                <div>
                                  <p className="text-sm font-bold text-red-700 dark:text-red-400">
                                    WhatsApp Disconnected
                                  </p>
                                  <p className="text-xs text-red-500 mt-1 leading-relaxed">
                                    Your WhatsApp connection was lost. Orders from retailers are 
                                    NOT being received until you reconnect.
                                  </p>
                                  {whatsappOrderPhone && (
                                    <p className="text-xs text-red-400 mt-2">
                                      Last connected: {whatsappOrderPhone}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-4 text-xs text-slate-500 dark:text-slate-400 leading-relaxed font-semibold">
                              <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">To reconnect:</p>
                              <ol className="list-decimal pl-4 space-y-1 text-slate-500 dark:text-slate-400 font-medium">
                                <li>Click "Reconnect WhatsApp" below</li>
                                <li>Scan the QR code with your WhatsApp</li>
                                <li>Orders will resume automatically</li>
                              </ol>
                            </div>

                            {evolutionError && (
                              <div className="p-4 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 rounded-xl text-xs font-semibold text-rose-800 dark:text-rose-300 flex items-center gap-2">
                                <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                                <span>{evolutionError}</span>
                              </div>
                            )}

                            <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-white/5 mt-6">
                              <button
                                type="button"
                                onClick={handleProvisionEvolution}
                                disabled={false}
                                className="px-6 py-2.5 bg-red-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-red-700 disabled:opacity-55 flex items-center gap-2 cursor-pointer transition-all"
                              >
                                <span>Reconnect WhatsApp</span>
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-4 flex gap-3 text-slate-600 dark:text-slate-400 text-xs leading-relaxed font-semibold">
                              <AlertCircle className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
                              <div>
                                <span className="text-slate-800 dark:text-slate-100 font-bold">Evolution API Connection Instructions:</span>
                                <ul className="list-disc pl-4 mt-1.5 space-y-1 text-slate-500 dark:text-slate-400 font-medium">
                                  <li>Click "Connect WhatsApp" to initialize the connection.</li>
                                  <li>The system will auto-generate a unique instance ID for your workspace.</li>
                                  <li>Scan the generated QR code using the "Link a Device" option in your WhatsApp app.</li>
                                  <li>The system will automatically detect the connection and activate the ingestion pipeline.</li>
                                </ul>
                              </div>
                            </div>

                            <form onSubmit={handleProvisionEvolution} className="space-y-5 mt-4">
                              {qrCodeBase64 && (provisioningStatus === "connecting" || provisioningStatus === "provisioning") && (
                                <div className="flex flex-col items-center justify-center p-6 bg-slate-50 dark:bg-dashboard-inset border border-dashed border-slate-200 dark:border-white/10 rounded-xl space-y-4">
                                  <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Scan this QR code with WhatsApp</p>
                                  <div className="bg-white dark:bg-dashboard-card p-4 rounded-xl shadow-md border border-slate-100 dark:border-white/5">
                                    <img src={qrCodeBase64} alt="WhatsApp QR Code" className="w-48 h-48" />
                                  </div>
                                  <p className="text-[10px] text-slate-400 font-semibold animate-pulse flex items-center gap-1.5">
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    <span>Waiting for scan authorization...</span>
                                  </p>
                                </div>
                              )}

                              {evolutionError && (
                                <div className="p-4 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 rounded-xl text-xs font-semibold text-rose-800 dark:text-rose-300 flex items-center gap-2">
                                  <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                                  <span>{evolutionError}</span>
                                </div>
                              )}

                              <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-white/5 mt-6">
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
                    )}
                  </div>
                )}

                {/* Razorpay Card */}
                {(activeTab === "All" || activeTab === "Payments") && (
                  <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-50 dark:bg-blue-500/10 rounded-xl flex items-center justify-center text-xl">
                          💳
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Razorpay</h3>
                          <p className="text-xs text-slate-400">Payment collection</p>
                        </div>
                      </div>
                      {razorpayConnected ? (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          {razorpayMode === "test" ? "Connected · Test Mode" : "Connected · Live"}
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/5 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          Not Connected
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                      Send UPI payment links to retailers on WhatsApp. Payments reconcile automatically.
                    </p>

                    <button
                      type="button"
                      onClick={() => setRazorpayExpanded(!razorpayExpanded)}
                      className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 cursor-pointer"
                    >
                      {razorpayExpanded ? "Hide details ▲" : (razorpayConnected ? "Manage →" : "Connect →")}
                    </button>

                    {/* Existing Razorpay connect/disconnect JSX — show when expanded */}
                    {razorpayExpanded && (
                      <div className="mt-4 pt-4 border-t border-slate-100 dark:border-white/5">
                        {razorpayConnected && !showUpdateForm ? (
                          <div className="space-y-4">
                            <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-4 flex flex-col gap-2 font-semibold">
                              <div className="flex justify-between items-center">
                                <span className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">Account Name</span>
                                <span className="text-sm text-slate-800 dark:text-slate-100">{accountName || "—"}</span>
                              </div>
                              <div className="flex justify-between items-center border-t border-slate-200/60 dark:border-white/[0.08] pt-2 mt-1">
                                <span className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">Key ID</span>
                                <span className="text-sm font-mono text-slate-800 dark:text-slate-100">{keyIdMasked}</span>
                              </div>
                            </div>

                            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100 dark:border-white/5 mt-6">
                              <button
                                type="button"
                                onClick={() => setShowUpdateForm(true)}
                                className="px-6 py-2.5 bg-slate-100 dark:bg-white/5 hover:bg-slate-200 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-bold shadow-sm cursor-pointer transition-all"
                              >
                                Update Keys
                              </button>
                              <button
                                type="button"
                                onClick={() => setShowRazorpayDisconnectModal(true)}
                                className="px-6 py-2.5 bg-rose-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-rose-700 cursor-pointer transition-all"
                              >
                                Disconnect
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 dark:border-white/[0.08] rounded-xl p-4 flex gap-3 text-slate-600 dark:text-slate-400 text-xs leading-relaxed font-semibold">
                              <ShieldCheck className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
                              <div>
                                <span className="text-slate-800 dark:text-slate-100 font-bold">Secure connection:</span>
                                <ul className="list-disc pl-4 mt-1.5 space-y-1 text-slate-500 dark:text-slate-400 font-medium">
                                  <li>Your secret key is encrypted with AES-256 and is never visible after saving.</li>
                                  <li>Keys are used only to generate payment links for your retailers.</li>
                                </ul>
                              </div>
                            </div>

                            <form onSubmit={handleRazorpayConnect} className="space-y-5 mt-4">
                              <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide">
                                  Razorpay Key ID *
                                </label>
                                <input
                                  type="text"
                                  value={keyIdInput}
                                  onChange={e => setKeyIdInput(e.target.value)}
                                  placeholder="rzp_test_xxxxxxxxxxxx"
                                  className="w-full px-4 py-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm font-medium bg-white dark:bg-dashboard-inset text-slate-700 dark:text-slate-200 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                                />
                              </div>

                              <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide">
                                  Razorpay Key Secret *
                                </label>
                                <div className="relative">
                                  <input
                                    type={showSecret ? "text" : "password"}
                                    value={keySecretInput}
                                    onChange={e => setKeySecretInput(e.target.value)}
                                    placeholder="••••••••••••••••••••••••••••••"
                                    className="w-full px-4 py-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm font-medium bg-white dark:bg-dashboard-inset text-slate-700 dark:text-slate-200 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all pr-12"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => setShowSecret(!showSecret)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                                  >
                                    {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                  </button>
                                </div>
                              </div>

                              {validationError && (
                                <div className="p-4 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 rounded-xl text-xs font-semibold text-rose-800 dark:text-rose-300 flex items-center gap-2">
                                  <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                                  <span>{validationError}</span>
                                </div>
                              )}

                              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-slate-100 dark:border-white/5 mt-6 gap-4">
                                <div className="flex flex-col gap-1.5">
                                  <a
                                    href="https://razorpay.com/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:underline"
                                  >
                                    <span>Don't have Razorpay? Create free account →</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                  <a
                                    href="https://dashboard.razorpay.com/app/keys"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:underline"
                                  >
                                    <span>Find your API keys →</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                </div>

                                <div className="flex gap-3 justify-end">
                                  {showUpdateForm && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setShowUpdateForm(false);
                                        setValidationError("");
                                        setKeyIdInput("");
                                        setKeySecretInput("");
                                      }}
                                      className="px-5 py-2.5 bg-slate-100 dark:bg-white/5 hover:bg-slate-200 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-bold cursor-pointer transition-all"
                                    >
                                      Cancel
                                    </button>
                                  )}
                                  <button
                                    type="submit"
                                    disabled={saving}
                                    className="px-6 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-emerald-700 disabled:opacity-55 flex items-center gap-2 cursor-pointer transition-all"
                                  >
                                    {saving ? (
                                      <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span>Connecting...</span>
                                      </>
                                    ) : (
                                      <span>Connect Razorpay Account</span>
                                    )}
                                  </button>
                                </div>
                              </div>
                            </form>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Coming Soon integrations */}
            {(activeTab === "All") && (
              <div className="mb-4">
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                  Coming Soon
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { icon: "📊", name: "Tally Prime", desc: "Export invoices and vouchers to Tally", category: "Accounting" },
                    { icon: "🚚", name: "Shiprocket", desc: "Auto-create shipments and track delivery", category: "Logistics" },
                    { icon: "🏦", name: "Marg ERP", desc: "Sync orders with Marg distribution software", category: "ERP" },
                    { icon: "📋", name: "GST Portal", desc: "Generate e-Invoice IRN for invoices above ₹5Cr", category: "Accounting" },
                  ].map(item => (
                    <div key={item.name} className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 p-5 opacity-70">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-slate-50 dark:bg-dashboard-inset rounded-xl flex items-center justify-center text-xl">
                            {item.icon}
                          </div>
                          <div>
                            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{item.name}</h3>
                            <p className="text-xs text-slate-400">{item.category}</p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold text-slate-400 bg-slate-100 dark:bg-white/5 px-2.5 py-1 rounded-full">
                          Coming Soon
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Request Integration */}
            <div className="bg-slate-50 dark:bg-dashboard-inset rounded-xl border border-slate-200 dark:border-white/10 p-6">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">
                Don&apos;t see what you need?
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Tell us which tool you use and we&apos;ll prioritize it.
              </p>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={integrationRequest}
                  onChange={e => setIntegrationRequest(e.target.value)}
                  placeholder="e.g. Marg ERP, Busy Accounting, Zoho..."
                  className="flex-1 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 bg-white dark:bg-dashboard-card"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (!integrationRequest.trim()) return;
                    window.location.href = `mailto:contact@distroos.in?subject=Integration Request: ${encodeURIComponent(integrationRequest)}&body=Hi, I would like to request an integration with ${encodeURIComponent(integrationRequest)}. I am using DistributorOS for my distribution business.`;
                    setIntegrationRequest("");
                  }}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg transition-all"
                >
                  Request
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-3">
                Or email us directly at{" "}
                <a href="mailto:contact@distroos.in" className="text-emerald-600 dark:text-emerald-400 hover:underline">
                  contact@distroos.in
                </a>
              </p>
            </div>

          </div>
        )}
      </main>

      {/* Disconnect WhatsApp Modal */}
      {showDisconnectModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-dashboard-card rounded-2xl shadow-xl max-w-md w-full border border-slate-100 dark:border-white/5 p-6 space-y-6 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-50 dark:bg-rose-500/10 rounded-full text-rose-600 dark:text-rose-400">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-950">Disconnect WhatsApp</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 font-semibold leading-relaxed font-semibold">
                  This will disconnect your WhatsApp. New orders will stop coming in. Are you sure?
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100 dark:border-white/5">
              <button
                type="button"
                disabled={disconnecting}
                onClick={() => setShowDisconnectModal(false)}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 rounded-lg text-sm font-bold cursor-pointer transition-all"
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

      {/* Disconnect Razorpay Modal */}
      {showRazorpayDisconnectModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-dashboard-card rounded-2xl shadow-xl max-w-md w-full border border-slate-100 dark:border-white/5 p-6 space-y-6 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-50 dark:bg-rose-500/10 rounded-full text-rose-600 dark:text-rose-400">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-950">Disconnect Razorpay</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 font-semibold leading-relaxed font-semibold">
                  This will disconnect your Razorpay integration. Retailers will no longer be able to make online payments. Are you sure?
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100 dark:border-white/5">
              <button
                type="button"
                disabled={disconnectingRazorpay}
                onClick={() => setShowRazorpayDisconnectModal(false)}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 rounded-lg text-sm font-bold cursor-pointer transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={disconnectingRazorpay}
                onClick={handleRazorpayDisconnect}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-bold shadow-md disabled:opacity-55 flex items-center gap-1.5 cursor-pointer transition-all"
              >
                {disconnectingRazorpay ? (
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
          <div className={`flex items-center gap-3 px-5 py-3 rounded-lg border shadow-xl bg-white dark:bg-dashboard-card ${
            toast.type === "success" 
              ? "border-emerald-200 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-300" 
              : "border-rose-200 dark:border-rose-500/20 text-rose-800 dark:text-rose-300"
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
