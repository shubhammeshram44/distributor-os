"use client";

import React from "react";
import { TrendingUp, TrendingDown, IndianRupee, ShoppingBag, BarChart, CreditCard } from "lucide-react";
import { DashboardMetrics } from "@/hooks/useDashboardData";

interface MetricCardsProps {
  metrics: DashboardMetrics | null;
}

export default function MetricCards({ metrics }: MetricCardsProps) {
  // Format numbers to Indian currency system (e.g. ₹ 28,45,600)
  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val);
  };

  const formatNumber = (val: number) => {
    return new Intl.NumberFormat("en-IN").format(val);
  };

  if (!metrics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white p-6 rounded-xl border border-dashboard-border shadow-sm animate-pulse h-32" />
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: "Total Sales (This Week)",
      value: formatCurrency(metrics.total_sales),
      change: `${metrics.total_sales_change}%`,
      isPositive: metrics.total_sales_change >= 0,
      subtext: "vs 14 May – 20 May, 2025",
      icon: IndianRupee,
      iconBg: "bg-emerald-50 text-emerald-600",
      strokeColor: "#10b981",
      sparklinePath: "M0,25 Q15,5 30,20 T60,10 T95,15 T130,5 T160,18" // green sparkline
    },
    {
      title: "Orders Count",
      value: formatNumber(metrics.orders_count),
      change: `${metrics.orders_count_change}%`,
      isPositive: metrics.orders_count_change >= 0,
      subtext: "vs last week",
      icon: ShoppingBag,
      iconBg: "bg-blue-50 text-blue-600",
      strokeColor: "#3b82f6",
      sparklinePath: "M0,20 Q15,28 30,10 T60,25 T90,5 T120,15 T160,8" // blue sparkline
    },
    {
      title: "Average Order Value",
      value: formatCurrency(metrics.average_order_value),
      change: `${metrics.average_order_value_change}%`,
      isPositive: metrics.average_order_value_change >= 0,
      subtext: "vs last week",
      icon: BarChart,
      iconBg: "bg-purple-50 text-purple-600",
      strokeColor: "#8b5cf6",
      sparklinePath: "M0,28 Q20,15 40,25 T80,10 T120,20 T160,12" // purple sparkline
    },
    {
      title: "Outstanding Collections",
      value: formatCurrency(metrics.outstanding_collections),
      change: `${Math.abs(metrics.outstanding_collections_change)}%`,
      isPositive: metrics.outstanding_collections_change < 0, // Positive is downward for outstanding collections
      subtext: "vs last week",
      icon: CreditCard,
      iconBg: "bg-orange-50 text-orange-600",
      strokeColor: "#f97316",
      sparklinePath: "M0,15 Q20,30 40,10 T80,25 T120,5 T160,20" // orange sparkline
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <div key={i} className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between hover:shadow-md transition-all">
            {/* Top Row */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center">
                {card.title}
              </span>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${card.iconBg}`}>
                <Icon className="w-4.5 h-4.5" />
              </div>
            </div>

            {/* Value and Trend Indicator */}
            <div className="mt-3 flex items-baseline gap-2">
              <h2 className="text-xl font-bold text-slate-800 tracking-tight">{card.value}</h2>
              <div className={`flex items-center gap-0.5 text-xs font-bold ${
                card.isPositive ? "text-emerald-600" : "text-rose-600"
              }`}>
                {card.isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                <span>{card.change}</span>
              </div>
            </div>

            {/* Bottom Sparkline and Subtext */}
            <div className="mt-4 flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-medium">{card.subtext}</span>
              
              {/* Micro-sparkline SVG */}
              <div className="w-24 h-8 overflow-hidden">
                <svg className="w-full h-full" viewBox="0 0 160 30">
                  <path
                    d={card.sparklinePath}
                    fill="none"
                    stroke={card.strokeColor}
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
