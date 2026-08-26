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
  const [authState, setAuthState] = useState<"checking" | "authenticated" | "reconnecting" | "unavailable" | "redirecting">(
    "checking"
  );
  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const verifySession = async () => {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      
      type RefreshResult =
        | { type: "success"; token: string }
        | { type: "unauthorized" }
        | { type: "transient_error" };

      const performRefresh = async (): Promise<RefreshResult> => {
        try {
          const resp = await fetch(`${apiBase}/api/v1/auth/refresh`, {
            method: "POST",
            credentials: "include",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
            },
          });
          if (resp.status === 200) {
            const data = await resp.json();
            if (data.access_token) {
              localStorage.setItem("accessToken", data.access_token);
              return { type: "success", token: data.access_token };
            }
          }
          if (resp.status === 401 || resp.status === 403) {
            return { type: "unauthorized" };
          }
          // Handle 408, 429, 5xx, or unexpected non-auth 4xx conservatively.
          // By returning transient_error instead of unauthorized, we do not clear
          // local credentials or redirect, and instead let the backoff retry kick in.
          return { type: "transient_error" };
        } catch (err) {
          console.error("Refresh request threw network/server error:", err);
          return { type: "transient_error" };
        }
      };

      const refreshSessionWithLocks = async (): Promise<RefreshResult> => {
        const tokenBeforeLock = localStorage.getItem("accessToken");
        
        if (typeof window !== "undefined" && window.navigator && window.navigator.locks) {
          return new Promise<RefreshResult>((resolve) => {
            window.navigator.locks.request("distributor_os_refresh_lock", async () => {
              try {
                const latestToken = localStorage.getItem("accessToken");
                if (latestToken && latestToken !== tokenBeforeLock) {
                  resolve({ type: "success", token: latestToken });
                  return;
                }
                const res = await performRefresh();
                resolve(res);
              } catch (err) {
                resolve({ type: "transient_error" });
              }
            });
          });
        } else {
          return performRefresh();
        }
      };

      let retries = 0;
      const delays = [1000, 2000, 4000, 8000];

      while (!cancelled) {
        try {
          let token = localStorage.getItem("accessToken");

          if (!token) {
            const refreshResult = await refreshSessionWithLocks();
            if (refreshResult.type === "success") {
              token = refreshResult.token;
            } else if (refreshResult.type === "unauthorized") {
              if (!cancelled) {
                setAuthState("redirecting");
                window.location.href = "/auth?expired=true";
              }
              return;
            } else {
              // refreshResult.type === "transient_error"
              throw new Error("Transient error during initial refresh");
            }
          }

          if (cancelled) return;

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

          if (resp.status === 200) {
            setAuthState("authenticated");
            return;
          }

          if (resp.status === 401 || resp.status === 403) {
            const refreshResult = await refreshSessionWithLocks();
            if (refreshResult.type === "success") {
              const retryResp = await fetch(`${apiBase}/api/v1/auth/me`, {
                method: "GET",
                credentials: "include",
                headers: {
                  Accept: "application/json",
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${refreshResult.token}`,
                },
              });

              if (cancelled) return;

              if (retryResp.status === 200) {
                setAuthState("authenticated");
                return;
              }
            } else if (refreshResult.type === "transient_error") {
              // Retain credentials and trigger the reconnecting backoff retry loop
              throw new Error("Transient error during refresh recovery");
            }

            if (refreshResult.type === "unauthorized" || refreshResult.type === "success") {
              localStorage.removeItem("accessToken");
              localStorage.removeItem("tenant_id");
              localStorage.removeItem("tenant_name");
              if (!cancelled) {
                setAuthState("redirecting");
                window.location.href = "/auth?expired=true";
              }
              return;
            }
          }

          throw new Error(`HTTP status ${resp.status}`);

        } catch (err: any) {
          if (cancelled) return;
          console.error("Dashboard verifySession iteration failed:", err);

          if (retries < delays.length) {
            setAuthState("reconnecting");
            const delay = delays[retries];
            retries++;
            await new Promise((resolve) => setTimeout(resolve, delay));
          } else {
            setAuthState("unavailable");
            return;
          }
        }
      }
    };

    verifySession();

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "accessToken" && e.newValue) {
        verifySession();
      }
    };
    window.addEventListener("storage", handleStorageChange);

    return () => {
      cancelled = true;
      window.removeEventListener("storage", handleStorageChange);
    };
  }, [retryTrigger]);

  if (authState !== "authenticated") {
    let content = null;
    if (authState === "checking") {
      content = (
        <div className="flex flex-col items-center justify-center h-full min-h-[400px] space-y-4">
          <div className="w-10 h-10 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">Checking your session…</p>
        </div>
      );
    } else if (authState === "reconnecting") {
      content = (
        <div className="flex flex-col items-center justify-center h-full min-h-[400px] space-y-4">
          <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 animate-pulse">Reconnecting to DistributorOS…</p>
        </div>
      );
    } else if (authState === "unavailable") {
      content = (
        <div className="flex flex-col items-center justify-center h-full min-h-[400px] space-y-4 max-w-md mx-auto text-center px-4">
          <div className="w-12 h-12 bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 rounded-full flex items-center justify-center text-rose-600 dark:text-rose-400 mb-2">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
            DistributorOS is temporarily unavailable. Your session has not been cleared.
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            We are having trouble reaching the server. Please verify your connection or click retry below.
          </p>
          <button
            onClick={() => {
              setAuthState("checking");
              setRetryTrigger(prev => prev + 1);
            }}
            className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow-md"
          >
            Retry
          </button>
        </div>
      );
    } else {
      // "redirecting"
      content = (
        <div className="flex flex-col items-center justify-center h-full min-h-[400px] space-y-4">
          <div className="w-10 h-10 border-4 border-slate-300 border-t-transparent rounded-full animate-spin" />
        </div>
      );
    }

    return (
      <div className="flex bg-dashboard-bg min-h-screen" aria-busy="true" aria-live="polite">
        {/* Sidebar shell skeleton */}
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

        {/* Main workspace shell */}
        <div className="flex-1 md:pl-64 flex flex-col h-screen overflow-hidden">
          <div className="h-16 border-b border-dashboard-border bg-white dark:bg-dashboard-card flex items-center justify-between px-6 shrink-0">
            <div className="h-9 w-72 rounded-lg bg-slate-100 dark:bg-white/5 animate-pulse" />
          </div>
          <main className="flex-1 p-6 overflow-y-auto">
            {content}
          </main>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
