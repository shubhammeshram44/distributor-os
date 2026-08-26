"use client";

import React, { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { Save, ShieldCheck } from "lucide-react";

export default function CustomerDefaultsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("My Workspace");
  const [creditLimit, setCreditLimit] = useState("5000");
  const [paymentTerms, setPaymentTerms] = useState("Net 30");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const authHeaders = (): Record<string, string> => {
    const token = localStorage.getItem("accessToken");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  useEffect(() => {
    const id = localStorage.getItem("tenant_id") || "";
    setTenantId(id);
    setTenantName(localStorage.getItem("tenant_name") || "My Workspace");
    if (!id) return;

    fetch(`${apiBase}/api/v1/customer-defaults?tenant_id=${id}`, {
      credentials: "include",
      headers: authHeaders(),
    })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "Could not load customer defaults");
        setCreditLimit(String(data.credit_limit));
        setPaymentTerms(data.payment_terms);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [apiBase]);

  const save = async () => {
    if (!tenantId) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/customer-defaults?tenant_id=${tenantId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          credit_limit: Number(creditLimit),
          payment_terms: paymentTerms.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save customer defaults");
      setMessage("Defaults saved. They will apply only to customers created from now on.");
    } catch (e: any) {
      setError(e.message || "Could not save customer defaults");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar activeTab="Customer Defaults" setActiveTab={() => {}} tenantName={tenantName} />
      <div className="md:ml-64 min-h-screen">
        <DashboardHeader tenantName={tenantName} onTenantChange={(id) => setTenantId(id)} />
        <main className="max-w-4xl mx-auto p-6 md:p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Customer Defaults</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Default commercial terms used when a new customer is created.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
            {loading ? (
              <p className="text-sm text-slate-500">Loading defaults…</p>
            ) : (
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">
                    New customer credit limit
                  </label>
                  <div className="relative max-w-xs">
                    <span className="absolute left-3 top-2.5 text-slate-500">₹</span>
                    <input
                      type="number"
                      min="0"
                      value={creditLimit}
                      onChange={(e) => setCreditLimit(e.target.value)}
                      className="w-full pl-8 pr-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">
                    Default payment terms
                  </label>
                  <select
                    value={paymentTerms}
                    onChange={(e) => setPaymentTerms(e.target.value)}
                    className="w-full max-w-xs px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  >
                    <option>Due on receipt</option>
                    <option>Net 7</option>
                    <option>Net 15</option>
                    <option>Net 30</option>
                    <option>Net 45</option>
                    <option>Net 60</option>
                  </select>
                </div>

                <div className="flex gap-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 p-4 text-sm text-amber-900 dark:text-amber-200">
                  <ShieldCheck className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <p>
                    These values are copied to a customer when the customer is created. Changing the defaults does not change existing customers. To change an individual customer's terms, go to Customers and edit that customer.
                  </p>
                </div>

                {message && <p className="text-sm text-emerald-700 dark:text-emerald-400">{message}</p>}
                {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

                <button
                  onClick={save}
                  disabled={saving || !paymentTerms.trim() || Number(creditLimit) < 0}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-semibold"
                >
                  <Save className="w-4 h-4" />
                  {saving ? "Saving…" : "Save defaults"}
                </button>

                <p className="text-xs text-slate-400">
                  Only Super Admin and Finance users can update these defaults.
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
