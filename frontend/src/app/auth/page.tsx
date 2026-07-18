"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Phone, Loader2, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import { RecaptchaVerifier, signInWithPhoneNumber, ConfirmationResult } from "firebase/auth";
import { auth, isFirebaseConfigured } from "@/lib/firebase";
import OtpInput from "@/components/ui/OtpInput";
import ThemeToggle from "@/components/ui/ThemeToggle";

function cleanAndNormalizePhone(input: string): string | null {
  const trimmed = input.trim();
  const digits = trimmed.replace(/\D/g, "");

  // Already in E.164 format (starts with +): strip non-digits and return
  if (trimmed.startsWith("+") && digits.length >= 10 && digits.length <= 15) {
    return `+${digits}`;
  }
  // Bare 10-digit Indian number → prepend +91
  if (digits.length === 10) return `+91${digits}`;
  // 12-digit with 91 country code but no leading + (e.g. 919876543210)
  if (digits.length === 12 && digits.startsWith("91")) return `+${digits}`;
  return null;
}

function getFirebaseErrorMessage(err: unknown): string {
  if (err instanceof Error) {
    const code = (err as any).code as string | undefined;
    const firebaseMessages: Record<string, string> = {
      "auth/too-many-requests": "Too many attempts. Please wait a few minutes before trying again.",
      "auth/invalid-phone-number": "The phone number you entered is invalid. Please check and try again.",
      "auth/quota-exceeded": "SMS quota exceeded. Please try again later.",
      "auth/captcha-check-failed": "reCAPTCHA verification failed. Please refresh and try again.",
      "auth/invalid-verification-code": "The code you entered is incorrect. Please try again.",
      "auth/code-expired": "The verification code has expired. Please request a new one.",
      "auth/session-expired": "Your session has expired. Please request a new OTP.",
      "auth/missing-verification-code": "Please enter the 6-digit verification code.",
      "auth/network-request-failed": "Network error. Please check your connection and try again.",
      "auth/user-disabled": "This account has been disabled. Please contact support.",
    };
    if (code && firebaseMessages[code]) return firebaseMessages[code];
    if (err.message) return err.message;
  }
  return "Something went wrong. Please try again.";
}

export default function AuthPage() {
  const router = useRouter();
  const [mobileNumber, setMobileNumber] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const confirmationRef = useRef<ConfirmationResult | null>(null);
  const recaptchaRef = useRef<RecaptchaVerifier | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const RESEND_COOLDOWN_SECONDS = 30;

  useEffect(() => {
    return () => {
      recaptchaRef.current?.clear();
      recaptchaRef.current = null;
    };
  }, []);

  // Countdown ticker for the resend cooldown.
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const getRecaptchaVerifier = () => {
    if (!auth) {
      throw new Error(
        "Phone authentication is not configured on this deployment. Please contact support."
      );
    }
    if (recaptchaRef.current) return recaptchaRef.current;
    recaptchaRef.current = new RecaptchaVerifier(auth, "recaptcha-container", {
      size: "invisible",
    });
    return recaptchaRef.current;
  };

  // Shared core used by both the initial "Send OTP" submit and "Resend OTP".
  // A fresh RecaptchaVerifier is required for resend since each verifier
  // instance is single-use once a signInWithPhoneNumber call resolves/fails.
  const sendOtp = async (e164: string) => {
    if (!auth) {
      throw new Error(
        "Phone authentication is not configured on this deployment. Please contact support."
      );
    }
    recaptchaRef.current?.clear();
    recaptchaRef.current = null;
    const verifier = getRecaptchaVerifier();
    confirmationRef.current = await signInWithPhoneNumber(auth, e164, verifier);
  };

  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const e164 = cleanAndNormalizePhone(mobileNumber);
    if (!e164) {
      setError("Please enter a valid mobile number (e.g. 98765 43210 or +91 98765 43210).");
      return;
    }

    setLoading(true);
    try {
      await sendOtp(e164);
      setSuccessMessage("Verification code sent to your phone.");
      setStep(2);
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err: unknown) {
      recaptchaRef.current?.clear();
      recaptchaRef.current = null;
      setError(getFirebaseErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0 || resending || loading) return;

    const e164 = cleanAndNormalizePhone(mobileNumber);
    if (!e164) {
      setError("Please enter a valid mobile number (e.g. 98765 43210 or +91 98765 43210).");
      setStep(1);
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setResending(true);
    try {
      await sendOtp(e164);
      setOtpCode("");
      setSuccessMessage("A new verification code has been sent to your phone.");
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err: unknown) {
      recaptchaRef.current?.clear();
      recaptchaRef.current = null;
      setError(getFirebaseErrorMessage(err));
    } finally {
      setResending(false);
    }
  };

  const verifyOtp = async (code: string) => {
    setError(null);
    setSuccessMessage(null);

    if (code.length !== 6) {
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
      const credential = await confirmationRef.current.confirm(code);
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
        router.push("/auth/onboarding");
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

      router.push("/dashboard");
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : getFirebaseErrorMessage(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    await verifyOtp(otpCode);
  };

  const handleChangePhone = () => {
    confirmationRef.current = null;
    recaptchaRef.current?.clear();
    recaptchaRef.current = null;
    setOtpCode("");
    setResendCooldown(0);
    setStep(1);
  };

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-dashboard-inset items-center justify-center p-4 relative">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div id="recaptcha-container" />
      <div className="w-full max-w-md bg-white dark:bg-dashboard-card border border-slate-200 dark:border-white/10 rounded-2xl shadow-xl p-8 flex flex-col justify-between">

        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto mb-4 text-white text-xl font-black shadow-md shadow-blue-200">
            D
          </div>
          <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 tracking-tight">Distributor OS</h2>
          <p className="text-xs text-slate-400 font-semibold mt-1">
            Secure workspace authentication & verification portal
          </p>
        </div>

        {!isFirebaseConfigured && (
          <div className="flex items-center gap-2 p-3.5 mb-5 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs font-semibold">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>
              Phone sign-in is temporarily unavailable (authentication service is not configured).
              Please contact support.
            </span>
          </div>
        )}

        {step === 1 ? (
          <form onSubmit={handleRequestOtp} className="space-y-5">
            <div>
              <label className="block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                Mobile Number
              </label>
              <div className="relative">
                <input
                  type="tel"
                  placeholder="e.g. +91 98765 43210"
                  value={mobileNumber}
                  onChange={(e) => setMobileNumber(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-slate-200 dark:border-white/10 rounded-xl text-sm font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500 bg-slate-50/20 dark:bg-white/5 text-slate-700 dark:text-slate-300"
                  disabled={loading}
                  required
                />
                <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3.5 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-xl text-rose-600 dark:text-rose-400 text-xs font-semibold">
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
              <label className="block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                Verification Code
              </label>
              <OtpInput
                value={otpCode}
                onChange={setOtpCode}
                onComplete={(code) => verifyOtp(code)}
                disabled={loading}
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3.5 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-xl text-rose-600 dark:text-rose-400 text-xs font-semibold">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {successMessage && (
              <div className="flex items-center gap-2 p-3.5 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-xl text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
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
                onClick={handleResendOtp}
                className="w-full py-2 bg-transparent text-blue-600 dark:text-blue-400 hover:text-blue-700 hover:bg-blue-50 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:text-slate-400 disabled:hover:bg-transparent disabled:cursor-not-allowed flex items-center justify-center gap-2"
                disabled={loading || resending || resendCooldown > 0}
              >
                {resending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Resending...</span>
                  </>
                ) : resendCooldown > 0 ? (
                  <span>Resend OTP in {resendCooldown}s</span>
                ) : (
                  <span>Didn't get the code? Resend OTP</span>
                )}
              </button>

              <button
                type="button"
                onClick={handleChangePhone}
                className="w-full py-2 bg-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 rounded-xl text-xs font-bold transition-all cursor-pointer"
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
