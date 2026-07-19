"use client";

import React from "react";

interface OrderPipelineCardProps {
  statusDistribution: Record<string, number>;
}

const STAGE_ORDER = ["Draft", "Pending", "Confirmed", "Dispatched", "Delivered", "Cancelled"];
const STAGE_COLORS: Record<string, string> = {
  Draft: "bg-slate-500",
  Pending: "bg-amber-500",
  Confirmed: "bg-blue-500",
  Dispatched: "bg-violet-500",
  Delivered: "bg-emerald-500",
  Cancelled: "bg-rose-500",
};

/** Order pipeline breakdown sourced from sales-overview's status_distribution. */
export default function OrderPipelineCard({ statusDistribution }: OrderPipelineCardProps) {
  const entries = STAGE_ORDER
    .filter((stage) => statusDistribution[stage] !== undefined)
    .map((stage) => ({ stage, count: statusDistribution[stage] }));

  // Include any stages returned by the API that aren't in our known ordering,
  // so nothing real is silently dropped.
  Object.keys(statusDistribution).forEach((stage) => {
    if (!STAGE_ORDER.includes(stage)) entries.push({ stage, count: statusDistribution[stage] });
  });

  const total = entries.reduce((sum, e) => sum + e.count, 0);

  return (
    <div className="bg-dashDark-card border border-dashDark-border rounded-xl p-5 h-full flex flex-col">
      <h3 className="font-bold text-dashDark-text text-sm mb-4">Order Pipeline</h3>

      {total === 0 ? (
        <p className="text-xs text-dashDark-textMuted flex-1 flex items-center justify-center">No orders yet</p>
      ) : (
        <>
          <div className="flex h-2.5 rounded-full overflow-hidden mb-4">
            {entries.map((e) => (
              e.count > 0 && (
                <div
                  key={e.stage}
                  className={STAGE_COLORS[e.stage] || "bg-dashDark-textFaint"}
                  style={{ width: `${(e.count / total) * 100}%` }}
                  title={`${e.stage}: ${e.count}`}
                />
              )
            ))}
          </div>
          <div className="space-y-2 flex-1">
            {entries.filter((e) => e.count > 0).map((e) => (
              <div key={e.stage} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${STAGE_COLORS[e.stage] || "bg-dashDark-textFaint"}`} />
                  <span className="text-dashDark-textMuted font-semibold">{e.stage}</span>
                </div>
                <span className="text-dashDark-text font-bold">{e.count}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
