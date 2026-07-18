"use client";

import React from "react";
import {
  ShoppingCart,
  IndianRupee,
  UserPlus,
  Box,
  Truck,
  Zap,
  ArrowRight
} from "lucide-react";
import { ActivityEvent } from "@/hooks/useDashboardData";
import Link from "next/link";
import { formatDateTime } from "@/utils/datetime";

interface ActivityFeedProps {
  activities: ActivityEvent[];
  viewAllHref?: string;
}

export default function ActivityFeed({ activities, viewAllHref }: ActivityFeedProps) {
  // Map event categories to visual icons and styles
  const getCategoryStyles = (category: string) => {
    switch (category.toLowerCase()) {
      case "order":
        return {
          icon: ShoppingCart,
          color: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 border-blue-100 dark:border-blue-500/20"
        };
      case "payment":
        return {
          icon: IndianRupee,
          color: "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-100 dark:border-emerald-500/20"
        };
      case "customer":
        return {
          icon: UserPlus,
          color: "text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-500/10 border-teal-100 dark:border-teal-500/20"
        };
      case "inventory":
        return {
          icon: Box,
          color: "text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border-indigo-100 dark:border-indigo-500/20"
        };
      case "delivery":
        return {
          icon: Truck,
          color: "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-500/10 border-orange-100 dark:border-orange-500/20"
        };
      default:
        return {
          icon: Zap,
          color: "text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-dashboard-inset border-slate-100 dark:border-white/5"
        };
    }
  };

  return (
    <div className="bg-white dark:bg-dashboard-card p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
        <h3 className="font-bold text-slate-800 dark:text-slate-100 text-base">Recent Activity</h3>
        {viewAllHref ? (
          <Link href={viewAllHref} className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View all</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        ) : (
          <button className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View all</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Activity Timeline List */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 py-1 max-h-[220px]">
        {activities.length === 0 ? (
          <div className="text-center text-slate-400 text-sm py-12">
            No recent activity logged.
          </div>
        ) : (
          activities.map((act, idx) => {
            const styles = getCategoryStyles(act.category);
            const Icon = styles.icon;
            return (
              <div key={idx} className="flex gap-3 items-start relative group">
                {/* Timeline Connector line */}
                {idx < activities.length - 1 && (
                  <div className="w-[1.5px] bg-slate-100 dark:bg-white/5 absolute left-4.5 top-9 bottom-[-16px] z-0 group-hover:bg-slate-200 transition-colors" />
                )}

                {/* Category Icon */}
                <div className={`w-9 h-9 rounded-full border flex items-center justify-center shrink-0 z-10 shadow-sm ${styles.color}`}>
                  <Icon className="w-4.5 h-4.5" />
                </div>

                {/* Event Message and Time */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 leading-snug truncate group-hover:text-slate-900 dark:hover:text-slate-100 transition-colors" title={act.message}>
                    {act.message}
                  </p>
                  <span className="text-[10px] text-slate-400 font-bold tracking-tight block mt-0.5">
                    {act.timestamp ? formatDateTime(act.timestamp, "relative") : act.time}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
