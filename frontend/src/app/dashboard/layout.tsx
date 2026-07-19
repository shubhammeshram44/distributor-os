"use client";

import React, { useEffect, useState } from "react";

/**
 * Client-side auth guard for every /dashboard/* route.
 *
 * Previously each dashboard page implemented its own ad-hoc auth check
 * (fetching /auth/me and redirecting on 401), which meant coverage was
 * inconsistent: some pages never checked auth at all and rendered the
 * full app shell + content to logged-out users (e.g. settings/payments),
 * while others (e.g. shipments) just caught the resulting 401 as a
 * generic fetch error and got stuck showing an error/spinner instead of
 * redirecting to /auth.
 *
 * This layout centralizes the check once for all nested routes: no
 * dashboard content — and no page-level data fetching — runs until
 * we've confirmed a valid session.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [authState, setAuthState] = useState<"checking" | "authenticated" | "redirecting">(
    "checking"
  );

  useEffect(() => {
    let cancelled = false;

    const verifySession = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const token = localStorage.getItem("accessToken");

        if (!token) {
          if (!cancelled) {
            setAuthState("redirecting");
            window.location.href = "/auth";
          }
          return;
        }

        const resp = await fetch(`${apiBase}/api/v1/auth/me`, {
          method: "GET",
          credentials: "include",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });

        if (cancelled) return;

        if (resp.status === 401 || resp.status === 403) {
          localStorage.removeItem("accessToken");
          localStorage.removeItem("tenant_id");
          localStorage.removeItem("tenant_name");
          setAuthState("redirecting");
          window.location.href = "/auth";
          return;
        }

        if (!resp.ok) {
          // Backend unreachable or errored — don't trap the user on a blank
          // screen forever; send them back to auth to re-establish session.
          setAuthState("redirecting");
          window.location.href = "/auth";
          return;
        }

        setAuthState("authenticated");
      } catch (err) {
        console.error("Dashboard auth guard: session verification failed:", err);
        if (!cancelled) {
          setAuthState("redirecting");
          window.location.href = "/auth";
        }
      }
    };

    verifySession();

    return () => {
      cancelled = true;
    };
  }, []);

  if (authState !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-dashboard-inset">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200 dark:border-blue-500/20 border-t-blue-600" />
      </div>
    );
  }

  return <>{children}</>;
}
