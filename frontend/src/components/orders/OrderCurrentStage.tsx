"use client";

import React from "react";
import { LifecycleStage, OperationalException } from "@/types/order";
import { AlertCircle, Clock, AlertTriangle, CheckCircle2 } from "lucide-react";

interface OrderCurrentStageProps {
  stage?: LifecycleStage;
  exception?: OperationalException | null;
  isCancelled?: boolean;
}

export default function OrderCurrentStage({
  stage,
  exception,
  isCancelled = false,
}: OrderCurrentStageProps) {
  if (isCancelled) {
    return (
      <div className="flex flex-col items-start gap-1">
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold leading-none bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-white/10">
          Cancelled
        </span>
      </div>
    );
  }

  const renderException = () => {
    if (!exception) return null;

    let icon = <AlertCircle className="w-3 h-3 shrink-0" />;
    let style = "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20";

    if (exception.severity === "error") {
      icon = <AlertTriangle className="w-3 h-3 shrink-0" />;
      style = "bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-500/20";
    } else if (exception.severity === "info") {
      icon = <Clock className="w-3 h-3 shrink-0" />;
      style = "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20";
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${style} max-w-[200px] truncate`}
        title={exception.actionHint || exception.label}
      >
        {icon}
        <span className="truncate">{exception.label}</span>
      </span>
    );
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex items-center gap-1.5">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold leading-none bg-slate-50 dark:bg-white/5 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-white/10 shadow-2xs">
          {stage?.name || "Processing"}
        </span>
      </div>
      {renderException()}
    </div>
  );
}
