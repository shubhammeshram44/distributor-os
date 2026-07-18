"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import {
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  XCircle,
  ExternalLink,
  ShieldCheck
} from "lucide-react";

export default function PaymentsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [connected, setConnected] = useState(false);
  const [keyIdMasked, setKeyIdMasked] = useState("");
  const [accountName, setAccountName] = useState("");
  const [mode, setMode] = useState("test");

  // Form states
  const [keyIdInput, setKeyIdInput] = useState("");
  const [keySecretInput, setKeySecretInput] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [showUpdateForm, setShowUpdateForm] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);
  const [validationError, setValidationError] = useState("");

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

  const fetchStatus = async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/razorpay-status?tenant_id=${activeTenantId}`, {
        credentials: "include"
      });
      if (resp.ok) {
        const data = await resp.json();
        setConnected(data.connected);
        setKeyIdMasked(data.key_id_masked || "");
        setAccountName(data.account_name || "");
        setMode(data.mode || "test");
      } else {
        showToast("Failed to fetch Razorpay connection status.", "error");
      }
    } catch (err) {
      console.error("Failed to load Razorpay status:", err);
      showToast("Error loading Razorpay configuration from server.", "error");
    } finally {
      setLoading(false);
    }
  };

  // Fetch integration settings from backend when activeTenantId resolves
  useEffect(() => {
    fetchStatus();
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

  const handleConnect = async (e: React.FormEvent) => {
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
        setConnected(true);
        setKeyIdMasked(data.key_id_masked || "");
        setAccountName(data.account_name || "");
        setMode(data.mode || "test");
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

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/tenant/razorpay-disconnect?tenant_id=${activeTenantId}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (resp.ok) {
        setConnected(false);
        setKeyIdMasked("");
        setAccountName("");
        setMode("test");
        showToast("Razorpay account disconnected.", "success");
      } else {
        const data = await resp.json();
        showToast(data.detail || "Failed to disconnect Razorpay.", "error");
      }
    } catch (err) {
      console.error("Disconnect failed:", err);
      showToast("Network error during disconnect request.", "error");
    } finally {
      setDisconnecting(false);
      setShowDisconnectModal(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC]">
      <Sidebar activeTab="Payments" setActiveTab={() => {}} tenantName={getTenantName()} />
      
      <div className="flex-1 flex flex-col md:pl-64 min-h-screen">
        <DashboardHeader onTenantChange={handleTenantChange} />
        
        <main className="flex-1 p-6 space-y-6 max-w-4xl w-full mx-auto">
          <div>
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-brand-blue" />
              <span>Payment Gateway Settings</span>
            </h1>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              Connect and manage your payment collection settings.
            </p>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <Loader2 className="w-10 h-10 text-brand-blue animate-spin" />
              <p className="text-sm font-semibold text-slate-400">Loading configurations...</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="bg-white dark:bg-dashboard-card rounded-xl border border-slate-200 dark:border-white/10 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
                  <div>
                    <h3 className="font-extrabold text-slate-800 dark:text-slate-100 text-base">Payment Collection</h3>
                    <p className="text-xs text-slate-400 font-semibold mt-0.5">
                      Connect your Razorpay account to collect payments from retailers automatically.
                    </p>
                  </div>
                  <div>
                    {connected && !showUpdateForm ? (
                      mode === "live" ? (
                        <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <span>Connected — Live Mode</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 border border-amber-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                          <AlertCircle className="w-4 h-4 text-amber-600" />
                          <span>Connected — Test Mode</span>
                        </span>
                      )
                    ) : (
                      <span className="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 border border-rose-200 px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                        <XCircle className="w-4 h-4 text-rose-600" />
                        <span>Not Connected</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {connected && !showUpdateForm ? (
                    <div className="space-y-4">
                      <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 rounded-xl p-4 flex flex-col gap-2 font-semibold">
                        <div className="flex justify-between items-center">
                          <span className="text-xs text-slate-500 dark:text-slate-500 uppercase tracking-wide">Account Name</span>
                          <span className="text-sm text-slate-800 dark:text-slate-100">{accountName || "—"}</span>
                        </div>
                        <div className="flex justify-between items-center border-t border-slate-200/60 pt-2 mt-1">
                          <span className="text-xs text-slate-500 dark:text-slate-500 uppercase tracking-wide">Key ID</span>
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
                          onClick={() => setShowDisconnectModal(true)}
                          className="px-6 py-2.5 bg-rose-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-rose-700 cursor-pointer transition-all"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="bg-slate-50 dark:bg-dashboard-inset border border-slate-200/60 rounded-xl p-4 flex gap-3 text-slate-600 dark:text-slate-400 text-xs leading-relaxed font-semibold">
                        <ShieldCheck className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
                        <div>
                          <span className="text-slate-800 dark:text-slate-100 font-bold">Secure connection:</span>
                          <ul className="list-disc pl-4 mt-1.5 space-y-1 text-slate-500 dark:text-slate-500 font-medium">
                            <li>Your secret key is encrypted with AES-256 and is never visible after saving.</li>
                            <li>Keys are used only to generate payment links for your retailers.</li>
                          </ul>
                        </div>
                      </div>

                      <form onSubmit={handleConnect} className="space-y-5">
                        <div className="space-y-1.5">
                          <label className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide">
                            Razorpay Key ID *
                          </label>
                          <input
                            type="text"
                            value={keyIdInput}
                            onChange={e => setKeyIdInput(e.target.value)}
                            placeholder="rzp_test_xxxxxxxxxxxx"
                            className="w-full px-4 py-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm font-medium focus:ring-2 focus:ring-brand-blue/20 focus:border-brand-blue outline-none transition-all"
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
                              className="w-full px-4 py-2.5 border border-slate-200 dark:border-white/10 rounded-lg text-sm font-medium focus:ring-2 focus:ring-brand-blue/20 focus:border-brand-blue outline-none transition-all pr-12"
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
                          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                            <span>{validationError}</span>
                          </div>
                        )}

                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-slate-100 dark:border-white/5 mt-6 gap-4">
                          <div className="flex flex-col gap-1.5">
                            <a
                              href="https://razorpay.com/"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-bold text-brand-blue hover:underline"
                            >
                              <span>Don't have Razorpay? Create free account →</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                            <a
                              href="https://dashboard.razorpay.com/app/keys"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-bold text-brand-blue hover:underline"
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
              </div>
            </div>
          )}
        </main>
      </div>

      {showDisconnectModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-dashboard-card rounded-2xl shadow-xl max-w-md w-full border border-slate-100 dark:border-white/5 p-6 space-y-6 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-50 rounded-full text-rose-600">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-950">Disconnect Razorpay</h3>
                <p className="text-sm text-slate-500 dark:text-slate-500 font-semibold leading-relaxed font-semibold">
                  This will disconnect your Razorpay integration. Retailers will no longer be able to make online payments. Are you sure?
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

      {/* Elegant Toast Notifications */}
      {toast.show && (
        <div className="fixed bottom-5 right-5 z-50 animate-slide-in">
          <div className={`flex items-center gap-3 px-5 py-3 rounded-lg border shadow-xl bg-white dark:bg-dashboard-card ${
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
