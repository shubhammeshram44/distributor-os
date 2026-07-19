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
      <div className="flex bg-dashboard-bg min-h-screen" aria-busy="true" aria-live="polite">
        {/* Sidebar shell skeleton — mirrors Sidebar.tsx's brand header + 10 nav rows,
            so session verification doesn't flash an empty page before the real
            app chrome mounts. */}
        <aside className="hidden md:flex w-64 bg-brand-dark flex-col h-screen fixed left-0 top-0 border-r border-brand-darkHover">
          <div className="h-16 flex items-center px-6 gap-2 border-b border-brand-darkHover">
            <div className="w-8 h-8 rounded bg-brand-blue flex items-center justify-center font-bold text-lg text-white">
              D
            </div>
            <span className="font-semibold text-lg tracking-wider text-white">DistributorOS</span>
          </div>
          <nav className="flex-1 px-4 py-6 space-y-1.5">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-9 rounded-lg bg-white/5 animate-pulse" style={{ animationDelay: `${i * 40}ms` }} />
            ))}
          </nav>
        </aside>

        {/* Main workspace shell skeleton */}
        <div className="flex-1 md:pl-64 flex flex-col h-screen overflow-hidden">
          <div className="h-16 border-b border-dashboard-border bg-white dark:bg-dashboard-card flex items-center justify-between px-6 shrink-0">
            <div className="h-9 w-72 rounded-lg bg-slate-100 dark:bg-white/5 animate-pulse" />
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-slate-100 dark:bg-white/5 animate-pulse" />
              <div className="h-8 w-8 rounded-full bg-slate-100 dark:bg-white/5 animate-pulse" />
              <div className="h-9 w-9 rounded-full bg-slate-100 dark:bg-white/5 animate-pulse" />
            </div>
          </div>
          <main className="flex-1 p-6 space-y-6 overflow-hidden">
            <div className="space-y-2">
              <div className="h-5 w-56 rounded bg-slate-100 dark:bg-white/5 animate-pulse" />
              <div className="h-3 w-72 rounded bg-slate-100 dark:bg-white/5 animate-pulse" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-32 rounded-xl border border-dashboard-border bg-white dark:bg-dashboard-card animate-pulse" />
              ))}
            </div>
            <div className="h-64 rounded-xl border border-dashboard-border bg-white dark:bg-dashboard-card animate-pulse" />
          </main>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
