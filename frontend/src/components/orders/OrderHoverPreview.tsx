"use client";

import React from "react";
import { OrderHoverPreviewData, LifecycleStage } from "@/types/order";
import {
  MessageSquare,
  Globe,
  Clock,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  User,
  ArrowRight,
  ChevronRight,
  X,
  Check,
} from "lucide-react";

interface OrderHoverPreviewProps {
  data: OrderHoverPreviewData;
  position?: { top: number; left: number };
  onAction?: (action: string, orderId: string) => void;
  onViewDetails?: (orderId: string) => void;
  onClose?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}

export default function OrderHoverPreview({
  data,
  position,
  onAction,
  onViewDetails,
  onClose,
  onMouseEnter,
  onMouseLeave,
}: OrderHoverPreviewProps) {
  if (!data) return null;

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const renderChannelIcon = (channel: string) => {
    if (channel.toLowerCase() === "whatsapp") {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20"
          title="WhatsApp Channel"
        >
          <MessageSquare className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
          <span>WhatsApp</span>
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20"
        title="B2B Portal Channel"
      >
        <Globe className="w-3 h-3 text-blue-600 dark:text-blue-400" />
        <span>Portal</span>
      </span>
    );
  };

  const renderExceptionBadge = () => {
    if (!data.exception) return null;

    let bgStyle =
      "bg-amber-50 dark:bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-500/30";
    let Icon = AlertTriangle;

    if (data.exception.severity === "critical") {
      bgStyle =
        "bg-rose-50 dark:bg-rose-500/10 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-500/30";
      Icon = AlertCircle;
    } else if (data.exception.severity === "info") {
      bgStyle =
        "bg-blue-50 dark:bg-blue-500/10 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-500/30";
      Icon = Clock;
    }

    return (
      <div
        className={`flex items-start gap-2 p-2.5 rounded-xl border text-xs ${bgStyle}`}
      >
        <Icon className="w-4 h-4 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="font-extrabold uppercase tracking-tight text-[11px]">
              {data.exception.title}
            </span>
            {data.exception.age && (
              <span className="text-[10px] opacity-80 shrink-0 font-medium">
                {data.exception.age}
              </span>
            )}
          </div>
          {data.explanation && (
            <p className="mt-0.5 text-xs font-medium leading-relaxed opacity-95">
              {data.explanation}
            </p>
          )}
        </div>
      </div>
    );
  };

  const handleNextActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.nextAction && onAction) {
      onAction(data.nextAction.action, data.orderId);
    }
  };

  const handleViewFullOrderClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onViewDetails) {
      onViewDetails(data.orderId);
    }
  };

  const stylePosition: React.CSSProperties = position
    ? {
        position: "fixed",
        top: `${position.top}px`,
        left: `${position.left}px`,
      }
    : {};

  return (
    <div
      role="dialog"
      aria-label={`Order ${data.internalId} preview`}
      style={stylePosition}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className="z-50 w-88 sm:w-96 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-white/10 shadow-2xl p-4 flex flex-col gap-3 text-slate-800 dark:text-slate-100 select-none animate-in fade-in zoom-in-95 duration-150"
    >
      {/* 1. Header / Identity */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-100 dark:border-white/5 pb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-extrabold text-brand-blue tracking-tight">
              {data.internalId}
            </span>
            {renderChannelIcon(data.channel)}
          </div>
          <h4
            className="text-xs font-bold text-slate-700 dark:text-slate-200 mt-1 truncate"
            title={data.customer}
          >
            {data.customer}
          </h4>
        </div>

        <div className="flex flex-col items-end gap-1 shrink-0">
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
              title="Close preview"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <span className="text-base font-black text-slate-900 dark:text-white tracking-tight">
            {formatCurrency(data.amount)}
          </span>
        </div>
      </div>

      {/* 2. Current State & Owner */}
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold border ${
              data.isCancelled
                ? "bg-slate-100 dark:bg-white/5 text-slate-500 border-slate-200 dark:border-white/10"
                : data.currentStage?.status === "completed"
                ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20"
                : data.currentStage?.status === "attention"
                ? "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20"
                : "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20"
            }`}
          >
            {data.isCancelled ? (
              <X className="w-3 h-3 text-rose-500" />
            ) : data.currentStage?.status === "completed" ? (
              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            ) : data.currentStage?.status === "attention" ? (
              <AlertTriangle className="w-3 h-3 text-amber-500" />
            ) : (
              <Clock className="w-3 h-3 text-blue-500" />
            )}
            <span>{data.currentStage?.name || "Processing"}</span>
          </span>
        </div>

        {data.owner && (
          <div className="flex items-center gap-1 text-[11px] font-semibold text-slate-500 dark:text-slate-400 truncate">
            <User className="w-3 h-3 text-slate-400 shrink-0" />
            <span className="truncate">
              Owner: <strong className="text-slate-700 dark:text-slate-200">{data.owner.role || data.owner.name}</strong>
            </span>
          </div>
        )}
      </div>

      {/* 3. Compact Lifecycle Stepper */}
      {data.lifecycle?.stages && data.lifecycle.stages.length > 0 && !data.isCancelled && (
        <div className="bg-slate-50/70 dark:bg-white/[0.03] border border-slate-100 dark:border-white/5 rounded-xl p-2.5">
          <div className="flex items-center justify-between gap-1">
            {data.lifecycle.stages.map((stage: LifecycleStage, idx: number) => {
              const isCurrent = stage.id === data.lifecycle.currentStageId;
              const isCompleted = data.lifecycle.completedStageIds?.includes(stage.id);

              return (
                <React.Fragment key={stage.id}>
                  {idx > 0 && (
                    <div
                      className={`h-0.5 flex-1 rounded-full ${
                        isCompleted || isCurrent
                          ? "bg-emerald-500/70 dark:bg-emerald-500/60"
                          : "bg-slate-200 dark:bg-white/10"
                      }`}
                    />
                  )}
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div
                      className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-extrabold ${
                        isCompleted
                          ? "bg-emerald-500 text-white"
                          : isCurrent
                          ? "bg-brand-blue text-white ring-2 ring-brand-blue/30"
                          : "border border-slate-300 dark:border-white/20 text-slate-400 bg-white dark:bg-dashboard-card"
                      }`}
                    >
                      {isCompleted ? <Check className="w-2.5 h-2.5 stroke-[3]" /> : idx + 1}
                    </div>
                    <span
                      className={`text-[9px] font-bold ${
                        isCurrent
                          ? "text-brand-blue"
                          : isCompleted
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-slate-400"
                      }`}
                    >
                      {stage.shortName || stage.name.slice(0, 3).toUpperCase()}
                    </span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Contextual Explanation / Exception Alert */}
      {renderExceptionBadge()}

      {!data.exception && data.explanation && (
        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-100 dark:border-white/5 text-xs text-slate-600 dark:text-slate-300 font-medium leading-relaxed">
          {data.explanation}
        </div>
      )}

      {/* 5. Relevant Context (Dynamic key-value pairs) */}
      {data.relevantContext && data.relevantContext.length > 0 && (
        <div className="grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-slate-50/50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/5 text-xs">
          {data.relevantContext.map((item, idx) => (
            <div key={idx} className="flex flex-col">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                {item.label}
              </span>
              <span className="font-bold text-slate-700 dark:text-slate-200 truncate mt-0.5" title={item.value}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 6. Next Action Section */}
      {data.nextAction && (
        <div className="flex flex-col gap-2 p-3 rounded-xl bg-brand-blue/5 dark:bg-brand-blue/10 border border-brand-blue/20">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-brand-blue">
              Next Action
            </span>
          </div>
          {data.nextAction.description && (
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 leading-snug">
              {data.nextAction.description}
            </p>
          )}
          <button
            onClick={handleNextActionClick}
            disabled={data.nextAction.enabled === false}
            className="w-full mt-1 py-2 px-3 bg-brand-blue hover:bg-brand-blueHover disabled:bg-slate-200 dark:disabled:bg-white/10 text-white disabled:text-slate-400 rounded-lg text-xs font-extrabold shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:cursor-not-allowed"
          >
            <span>{data.nextAction.label}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 7. Footer: View Full Order */}
      <div className="pt-2 border-t border-slate-100 dark:border-white/5 flex items-center justify-between">
        <span className="text-[10px] font-semibold text-slate-400">
          Captured: {new Date(data.createdOn).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
        </span>
        <button
          onClick={handleViewFullOrderClick}
          className="inline-flex items-center gap-1 text-xs font-extrabold text-brand-blue hover:text-brand-blueHover cursor-pointer group/link hover:underline"
        >
          <span>View Full Order</span>
          <ChevronRight className="w-3.5 h-3.5 group-hover/link:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </div>
  );
}
