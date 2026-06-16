"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Phone, KeyRound, Loader2, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import { RecaptchaVerifier, signInWithPhoneNumber, ConfirmationResult } from "firebase/auth";
import { auth } from "@/lib/firebase";

function normalizePhone(input: string): string {
  const raw = input.trim().replace(/[\s-]/g, "");
  if (raw.startsWith("+")) return raw;
  if (raw.startsWith("91") && raw.length === 12) return `+${raw}`;
  if (raw.length === 10) return `+91${raw}`;
  return `+${raw}`;
}

export default function AuthPage() {
  const router = useRouter();
  const [mobileNumber, setMobileNumber] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const confirmationRef = useRef<ConfirmationResult | null>(null);
  const recaptchaRef = useRef<RecaptchaVerifier | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    return () => {
      recaptchaRef.current?.clear();
      recaptchaRef.current = null;
    };
  }, []);

  const getRecaptchaVerifier = () => {
    if (recaptchaRef.current) return recaptchaRef.current;
    recaptchaRef.current = new RecaptchaVerifier(auth, "recaptcha-container", {
      size: "invisible",
    });
    return recaptchaRef.current;
  };

  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const cleanMobile = mobileNumber.replace(/\D/g, "");
    if (cleanMobile.length < 10) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }

    setLoading(true);
    try {
      const e164 = normalizePhone(mobileNumber);
      const verifier = getRecaptchaVerifier();
      confirmationRef.current = await signInWithPhoneNumber(auth, e164, verifier);
      setSuccessMessage("Verification code sent to your phone.");
      setStep(2);
    } catch (err: unknown) {
      recaptchaRef.current?.clear();
      recaptchaRef.current = null;
      const message = err instanceof Error ? err.message : "Failed to send OTP. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (otpCode.length !== 6) {
      setError("Please enter the 6-digit verification code.");
      return;
    }

    if (!confirmationRef.current) {
      setError("Session expired. Please request a new code.");
      setStep(1);
      return;
    }

    setLoading(true);
    try {
      const credential = await confirmationRef.current.confirm(otpCode);
      const firebaseToken = await credential.user.getIdToken();

      const response = await fetch(`${apiBase}/api/v1/auth/firebase-login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ firebase_token: firebaseToken }),
      });

      const resData = await response.json();
      if (!response.ok) {
        throw new Error(resData.detail || "Authentication failed.");
      }

      setSuccessMessage("Verified! Directing to workspace...");

      if (resData.is_new_user) {
        localStorage.setItem("signup_token", resData.signup_token || "");
        localStorage.setItem("userPhoneNumber", resData.phone_number || "");
        localStorage.removeItem("accessToken");
        localStorage.removeItem("tenant_id");
        setTimeout(() => router.push("/auth/onboarding"), 1000);
        return;
      }

      const activeTenantId = resData.tenant_id || resData.user?.tenant_id || "";
      localStorage.setItem("tenant_id", activeTenantId);
      localStorage.setItem("userRole", resData.user?.role || "");
      localStorage.setItem("userFullName", resData.user?.full_name || "");
      localStorage.setItem("userPhoneNumber", resData.user?.phone_number || "");
      localStorage.setItem("accessToken", resData.token || resData.access_token || "");
      localStorage.removeItem("signup_token");

      if (resData.tenant_name) {
        localStorage.setItem("tenant_name", resData.tenant_name);
      }

      setTimeout(() => router.push("/dashboard"), 1000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to verify OTP.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleChangePhone = () => {
    confirmationRef.current = null;
    recaptchaRef.current?.clear();
    recaptchaRef.current = null;
    setOtpCode("");
    setStep(1);
  };

  return (
    <div className="flex min-h-screen bg-slate-50 items-center justify-center p-4">
      <div id="recaptcha-container" />
      <div className="w-full max-w-md bg-white border border-slate-150 rounded-2xl shadow-xl p-8 flex flex-col justify-between">

        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto mb-4 text-white text-xl font-black shadow-md shadow-blue-200">
            D
          </div>
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Distributor OS</h2>
          <p className="text-xs text-slate-400 font-semibold mt-1">
            Secure workspace authentication & verification portal
          </p>
        </div>

        {step === 1 ? (
          <form onSubmit={handleRequestOtp} className="space-y-5">
            <div>
              <label className="block text-[11px] font-bold text-slate-500 mb-1.5 uppercase tracking-wider">
                Mobile Number
              </label>
              <div className="relative">
                <input
                  type="tel"
                  placeholder="e.g. +91 98765 43210"
                  value={mobileNumber}
                  onChange={(e) => setMobileNumber(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl text-sm font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500 bg-slate-50/20 text-slate-700"
                  disabled={loading}
                  required
                />
                <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3.5 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs font-semibold">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl text-sm font-bold transition-all shadow-md shadow-blue-100 flex items-center justify-center gap-2 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Sending OTP...</span>
                </>
              ) : (
                <>
                  <span>Send OTP via SMS</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="space-y-5">
            <div>
              <label className="block text-[11px] font-bold text-slate-500 mb-1.5 uppercase tracking-wider">
                Verification Code
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Enter 6-digit OTP code"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl text-sm font-semibold tracking-widest text-center focus:outline-none focus:ring-1 focus:ring-blue-500 bg-slate-50/20 text-slate-700"
                  disabled={loading}
                  required
                />
                <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3.5 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs font-semibold">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {successMessage && (
              <div className="flex items-center gap-2 p-3.5 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-600 text-xs font-semibold">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl text-sm font-bold transition-all shadow-md shadow-blue-100 flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Verifying OTP...</span>
                  </>
                ) : (
                  <>
                    <span>Verify Code & Launch</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleChangePhone}
                className="w-full py-2 bg-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded-xl text-xs font-bold transition-all cursor-pointer"
                disabled={loading}
              >
                Change Phone Number
              </button>
            </div>
          </form>
        )}

        <div className="mt-8 text-center">
          <p className="text-[10px] text-slate-400 font-semibold leading-relaxed">
            By authenticating, you agree to our Terms of Service & Privacy Policy.<br />
            Secure phone verification powered by Firebase Authentication.
          </p>
        </div>

      </div>
    </div>
  );
}
