"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Circle, Rocket, X, ArrowRight } from "lucide-react";

interface OnboardingStep {
  key: string;
  label: string;
  done: boolean;
}

interface OnboardingStatus {
  is_new_workspace: boolean;
  completed_count: number;
  total_count: number;
  steps: OnboardingStep[];
}

interface OnboardingChecklistProps {
  activeTenantId: string;
}

// Maps each backend step key to where the user should go to complete it.
const STEP_LINKS: Record<string, string> = {
  add_product: "/dashboard/products",
  add_customer: "/dashboard/customers",
  connect_whatsapp: "/dashboard/settings/integrations",
  connect_razorpay: "/dashboard/settings/payments",
  first_order: "/dashboard/orders",
};

const DISMISS_KEY_PREFIX = "onboarding_checklist_dismissed_";

/**
 * "Getting Started" checklist shown to brand-new tenants with an empty
 * workspace. Every completion flag is fetched live from the backend
 * (real product/customer/order/integration checks) — nothing here is
 * simulated. Helps address the "signed up but didn't know what to do next"
 * drop-off problem for first-time distributors.
 */
export default function OnboardingChecklist({ activeTenantId }: OnboardingChecklistProps) {
  const router = useRouter();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!activeTenantId) return;
    setDismissed(localStorage.getItem(`${DISMISS_KEY_PREFIX}${activeTenantId}`) === "true");
  }, [activeTenantId]);

  useEffect(() => {
    if (!activeTenantId) return;

    const fetchStatus = async () => {
      setLoading(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const resp = await fetch(`${apiBase}/api/v1/dashboard/onboarding-status?tenant_id=${activeTenantId}`, {
          credentials: "include",
        });
        if (resp.ok) {
          const data = await resp.json();
          setStatus(data);
        }
      } catch (err) {
        console.error("Failed to load onboarding status:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [activeTenantId]);

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(`${DISMISS_KEY_PREFIX}${activeTenantId}`, "true");
  };

  // Don't render anything while loading, if the fetch failed, if the user
  // dismissed it, or once every step is complete.
  if (loading || !status || dismissed || status.completed_count === status.total_count) {
    return null;
  }

  const progressPct = Math.round((status.completed_count / status.total_count) * 100);

  return (
    <div className="bg-white dark:bg-dashboard-card rounded-xl border border-dashboard-border shadow-sm overflow-hidden">
      <div className="p-5 flex items-start justify-between gap-4 border-b border-slate-100 dark:border-white/5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-500/10 text-brand-blue flex items-center justify-center shrink-0">
            <Rocket className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100">Getting Started</h2>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">
              {status.completed_count} of {status.total_count} steps complete — finish these to unlock your first order.
            </p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-50 dark:hover:bg-white/5 transition-all shrink-0"
          title="Hide checklist"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-5 pt-4">
        <div className="w-full h-1.5 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-blue rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <ul className="p-5 space-y-1">
        {status.steps.map((step) => (
          <li key={step.key}>
            <button
              type="button"
              onClick={() => !step.done && router.push(STEP_LINKS[step.key] || "/dashboard")}
              disabled={step.done}
              className={`w-full flex items-center gap-3 p-2.5 rounded-lg text-left transition-all ${
                step.done
                  ? "cursor-default"
                  : "hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer group"
              }`}
            >
              {step.done ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
              ) : (
                <Circle className="w-5 h-5 text-slate-300 shrink-0" />
              )}
              <span className={`text-sm font-semibold flex-1 ${step.done ? "text-slate-400 line-through" : "text-slate-700 dark:text-slate-300"}`}>
                {step.label}
              </span>
              {!step.done && (
                <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-brand-blue transition-all shrink-0" />
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
