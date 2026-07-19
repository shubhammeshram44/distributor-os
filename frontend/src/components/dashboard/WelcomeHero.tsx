"use client";

import React, { useEffect, useState } from "react";
import { Calendar, Plus } from "lucide-react";

interface WelcomeHeroProps {
  firstName: string;
  onNewOrder: () => void;
}

/**
 * Greeting banner for the Dashboard home page. Purely presentational —
 * the actual Timeframe/Customize controls (existing production feature)
 * render alongside it in page.tsx, this component only owns the
 * greeting + live date badge + primary "New Order" CTA.
 */
export default function WelcomeHero({ firstName, onNewOrder }: WelcomeHeroProps) {
  const [now, setNow] = useState<Date | null>(null);

  // Avoid SSR/client render mismatch — only render the live clock after mount.
  useEffect(() => {
    setNow(new Date());
    const interval = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(interval);
  }, []);

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  })();

  const dateLabel = now
    ? now.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })
    : "";
  const dayTimeLabel = now
    ? `${now.toLocaleDateString("en-IN", { weekday: "short" })}, ${now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`
    : "";

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 className="text-xl font-bold text-dashDark-text tracking-tight flex items-center gap-2">
          <span aria-hidden="true">👋</span>
          {greeting}{firstName ? `, ${firstName}!` : "!"}
        </h1>
        <p className="text-xs text-dashDark-textMuted font-semibold mt-0.5">
          Here&apos;s what&apos;s happening with your business today.
        </p>
      </div>

      <div className="flex items-center gap-3">
        {now && (
          <div className="hidden md:flex items-center gap-2 px-3 py-2 bg-dashDark-cardAlt border border-dashDark-border rounded-lg">
            <Calendar className="w-3.5 h-3.5 text-dashDark-textMuted" />
            <div className="leading-tight">
              <p className="text-xs font-bold text-dashDark-text">{dateLabel}</p>
              <p className="text-[10px] text-dashDark-textMuted">{dayTimeLabel}</p>
            </div>
          </div>
        )}
        <button
          onClick={onNewOrder}
          className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-sm transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Order</span>
        </button>
      </div>
    </div>
  );
}
