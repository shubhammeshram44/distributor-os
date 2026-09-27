"use client";

import React, { useState } from "react";
import { LifecycleStage } from "@/types/order";
import { Check, XCircle } from "lucide-react";

interface OrderLifecycleProgressProps {
  stages: LifecycleStage[];
  currentStageId: string;
  completedStageIds?: string[];
  isCancelled?: boolean;
  compact?: boolean;
}

/**
 * OrderLifecycleProgress
 * A reusable, compact visualization of order progression.
 * Architectural guarantee:
 * - Does NOT hardcode stage names or IDs.
 * - Renders any arbitrary sequence of stages provided by data or tenant configuration.
 */
export default function OrderLifecycleProgress({
  stages,
  currentStageId,
  completedStageIds = [],
  isCancelled = false,
  compact = true,
}: OrderLifecycleProgressProps) {
  const [hoveredStage, setHoveredStage] = useState<LifecycleStage | null>(null);

  if (!stages || stages.length === 0) {
    return null;
  }

  const currentIndex = stages.findIndex((s) => s.id === currentStageId);
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  if (isCancelled) {
    return (
      <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
        <XCircle className="w-3.5 h-3.5 shrink-0" />
        <span>Halted (Cancelled)</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 select-none group/lifecycle py-0.5">
      {/* Mini Stepper Line */}
      <div className="flex items-center gap-0.5">
        {stages.map((stage, idx) => {
          const isCurrent = stage.id === currentStageId;
          const isCompleted =
            completedStageIds.includes(stage.id) ||
            (!completedStageIds.length && idx < activeIndex);
          const isUpcoming = !isCurrent && !isCompleted;

          return (
            <React.Fragment key={stage.id}>
              {/* Connector line before (except first) */}
              {idx > 0 && (
                <div
                  className={`h-0.5 w-2.5 sm:w-3.5 rounded-full transition-colors ${
                    isCompleted || isCurrent
                      ? "bg-emerald-500/80 dark:bg-emerald-500/60"
                      : "bg-slate-200 dark:bg-white/10"
                  }`}
                />
              )}

              {/* Node Indicator */}
              <div
                className="relative cursor-pointer"
                onMouseEnter={() => setHoveredStage(stage)}
                onMouseLeave={() => setHoveredStage(null)}
                title={`${stage.sequence}. ${stage.name}`}
              >
                {isCompleted ? (
                  <div className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[9px] font-bold shadow-xs">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                ) : isCurrent ? (
                  <div className="relative flex items-center justify-center">
                    <span className="animate-ping absolute inline-flex h-3.5 w-3.5 rounded-full bg-brand-blue opacity-50" />
                    <div className="w-4 h-4 rounded-full bg-brand-blue text-white flex items-center justify-center text-[9px] font-extrabold shadow-sm ring-2 ring-brand-blue/30">
                      {stage.sequence}
                    </div>
                  </div>
                ) : (
                  <div className="w-3.5 h-3.5 rounded-full border border-slate-300 dark:border-white/20 bg-slate-100 dark:bg-dashboard-inset flex items-center justify-center text-[8px] text-slate-400 font-semibold" />
                )}

                {/* Micro Tooltip */}
                {hoveredStage?.id === stage.id && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded bg-slate-900 text-white text-[10px] font-medium whitespace-nowrap shadow-lg z-30 pointer-events-none">
                    <span className="font-bold">{stage.sequence}. {stage.name}</span>
                    <span className="text-slate-300 ml-1">
                      {isCurrent
                        ? "(Current)"
                        : isCompleted
                        ? "(Done)"
                        : "(Upcoming)"}
                    </span>
                  </div>
                )}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Stage Summary Label */}
      <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400 font-medium">
        <span className="font-semibold text-slate-700 dark:text-slate-300">
          {stages[activeIndex]?.name}
        </span>
        <span className="text-[10px] text-slate-400">
          ({activeIndex + 1}/{stages.length})
        </span>
      </div>
    </div>
  );
}
