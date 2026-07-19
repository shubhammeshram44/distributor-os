"use client";

import React from "react";
import { Sparkles, TrendingUp, TrendingDown } from "lucide-react";

interface AIInsightsCardProps {
  salesChange?: number;
  ordersChange?: number;
  collectionsChange?: number;
  lowStockCount: number;
}

/**
 * Short, plain-language summaries derived strictly from the *_change
 * percentages and counts the backend already computes (no invented
 * numbers/predictions) — presented as quick "insights" rather than raw stats.
 */
export default function AIInsightsCard({ salesChange, ordersChange, collectionsChange, lowStockCount }: AIInsightsCardProps) {
  const insights: { text: string; positive: boolean }[] = [];

  if (typeof salesChange === "number" && salesChange !== 0) {
    insights.push({
      text: `Sales are ${salesChange > 0 ? "up" : "down"} ${Math.abs(salesChange).toFixed(1)}% vs the previous period.`,
      positive: salesChange > 0,
    });
  }
  if (typeof ordersChange === "number" && ordersChange !== 0) {
    insights.push({
      text: `Order volume ${ordersChange > 0 ? "grew" : "declined"} by ${Math.abs(ordersChange).toFixed(1)}% recently.`,
      positive: ordersChange > 0,
    });
  }
  if (typeof collectionsChange === "number" && collectionsChange !== 0) {
    insights.push({
      text: `Outstanding collections ${collectionsChange > 0 ? "increased" : "reduced"} by ${Math.abs(collectionsChange).toFixed(1)}%.`,
      positive: collectionsChange < 0,
    });
  }
  if (lowStockCount > 0) {
    insights.push({
      text: `${lowStockCount} product${lowStockCount === 1 ? "" : "s"} may need restocking soon.`,
      positive: false,
    });
  }

  return (
    <div className="bg-gradient-to-br from-brand-blue/10 via-dashDark-card to-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-brand-blue/15 flex items-center justify-center">
          <Sparkles className="w-3.5 h-3.5 text-brand-blue" />
        </div>
        <h3 className="font-bold text-dashDark-text text-sm">Insights</h3>
      </div>

      {insights.length === 0 ? (
        <p className="text-xs text-dashDark-textMuted flex-1 flex items-center justify-center text-center">
          Not enough trend data yet — check back after more activity.
        </p>
      ) : (
        <div className="space-y-3 flex-1">
          {insights.slice(0, 4).map((insight, i) => (
            <div key={i} className="flex items-start gap-2">
              {insight.positive ? (
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
              )}
              <p className="text-xs text-dashDark-textMuted font-medium leading-snug">{insight.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
