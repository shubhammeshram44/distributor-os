"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Building2, Sparkles, ArrowRight, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [businessName, setBusinessName] = useState("");
  const [category, setCategory] = useState("FMCG");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [signupToken, setSignupToken] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("signup_token");
    if (!token) {
      router.push("/auth");
      return;
    }
    setSignupToken(token);
  }, [router]);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!businessName.trim()) {
      setError("Please enter your Business Name.");
      return;
    }
    if (!signupToken) {
      setError("Signup session expired. Please log in again.");
      router.push("/auth");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const signupResponse = await fetch(`${apiBase}/api/v1/auth/signup`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signup_token: signupToken,
          full_name: businessName.trim(),
        }),
      });

      const signupData = await signupResponse.json();
      if (!signupResponse.ok) {
        throw new Error(signupData.detail || "Failed to complete registration.");
      }

      const sessionToken = signupData.token || signupData.access_token || "";
      const activeTenantId = signupData.tenant_id || signupData.user?.tenant_id || "";

      localStorage.setItem("accessToken", sessionToken);
      localStorage.setItem("tenant_id", activeTenantId);
      localStorage.setItem("userRole", signupData.user?.role || "");
      localStorage.setItem("userFullName", signupData.user?.full_name || "");
      localStorage.setItem("userPhoneNumber", signupData.user?.phone_number || "");
      localStorage.removeItem("signup_token");

      if (signupData.tenant_name) {
        localStorage.setItem("tenant_name", signupData.tenant_name);
      }

      const profileResponse = await fetch(`${apiBase}/api/v1/tenant/profile`, {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: JSON.stringify({
          name: businessName.trim(),
          category: category,
        }),
      });

      const profileData = await profileResponse.json();
      if (!profileResponse.ok) {
        throw new Error(profileData.detail || "Failed to update tenant profile.");
      }

      if (profileData.tenant?.name) {
        localStorage.setItem("tenant_name", profileData.tenant.name);
      }

      setStep(2);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleLaunch = () => {
    router.push("/dashboard");
  };

  if (!signupToken) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/50 items-center justify-center p-6">
      <div className="w-full max-w-lg bg-white border border-slate-100/80 rounded-3xl shadow-2xl p-10 flex flex-col justify-between relative overflow-hidden">

        <div className="absolute -top-10 -right-10 w-32 h-32 bg-blue-400/10 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-indigo-400/10 rounded-full blur-2xl pointer-events-none" />

        <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              step === 1 ? "bg-blue-600 text-white ring-4 ring-blue-100" : "bg-emerald-100 text-emerald-700"
            }`}>
              {step === 1 ? "1" : <CheckCircle2 className="w-5 h-5" />}
            </div>
            <span className={`text-xs font-bold ${step === 1 ? "text-slate-800" : "text-slate-400"}`}>
              Business Profile
            </span>
          </div>
          <div className="w-8 h-[2px] bg-slate-200 flex-1 mx-4" />
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              step === 2 ? "bg-blue-600 text-white ring-4 ring-blue-100" : "bg-slate-100 text-slate-400"
            }`}>
              2
            </div>
            <span className={`text-xs font-bold ${step === 2 ? "text-slate-800" : "text-slate-400"}`}>
              Setup Complete
            </span>
          </div>
        </div>

        {step === 1 ? (
          <div>
            <div className="mb-8">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center mb-4 text-blue-600">
                <Building2 className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Configure Your Workspace</h2>
              <p className="text-sm text-slate-500 mt-1">
                Tell us about your business to get started with Distributor OS.
              </p>
            </div>

            <form onSubmit={handleProfileSubmit} className="space-y-6">
              <div>
                <label className="block text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider">
                  Business Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. S.V. Distributors"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-slate-50/20 text-slate-700 transition-all placeholder:text-slate-300"
                  disabled={loading}
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider">
                  Primary Category
                </label>
                <div className="relative">
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-slate-50/20 text-slate-700 transition-all appearance-none cursor-pointer"
                    disabled={loading}
                  >
                    <option value="FMCG">FMCG</option>
                    <option value="Beverages">Beverages</option>
                    <option value="Grocery">Grocery</option>
                    <option value="Pharma">Pharma</option>
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
                    <ChevronDownIcon />
                  </div>
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs font-semibold">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-blue-100 flex items-center justify-center gap-2 cursor-pointer mt-8"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Saving Profile...</span>
                  </>
                ) : (
                  <>
                    <span>Continue Setup</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          <div className="text-center">
            <div className="w-16 h-16 rounded-3xl bg-blue-600 flex items-center justify-center mx-auto mb-6 text-white shadow-xl shadow-blue-200 animate-bounce">
              <Sparkles className="w-8 h-8" />
            </div>

            <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Your Workspace is Ready!</h2>
            <p className="text-xs text-slate-400 font-bold mt-1 uppercase tracking-widest text-blue-600">
              WhatsApp AI Ingestion Activated
            </p>

            <div className="my-8 p-6 bg-slate-50/50 border border-slate-100 rounded-2xl text-left shadow-inner">
              <p className="text-sm text-slate-600 leading-relaxed font-medium">
                Welcome to <strong>DistributorOS</strong>! Your AI automated warehouse engine is ready. To process your first order, simply forward a text list from any retail client to your active WhatsApp number. The system parses line quantities and generates an active draft invoice instantly.
              </p>
            </div>

            <button
              onClick={handleLaunch}
              className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all shadow-xl shadow-blue-200 flex items-center justify-center gap-2 cursor-pointer hover:scale-[1.01] active:scale-[0.99]"
            >
              <span>Launch My Workspace 🚀</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
    </svg>
  );
}
