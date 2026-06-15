"use client";

import React from "react";
import { ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { DonutSegment } from "@/hooks/useDashboardData";
import Link from "next/link";

interface CollectionsDonutProps {
  data: DonutSegment[];
  viewReportHref?: string;
  overdue60Count?: number;
}

const COLORS = ["#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]; // Green, Amber, Red, Purple

export default function CollectionsDonut({ data, viewReportHref, overdue60Count }: CollectionsDonutProps) {
  // Sum outstanding total
  const totalOutstanding = data.reduce((sum, item) => sum + item.value, 0);

  // Format amount to Lakhs (e.g. 21,37,200 -> 21.37L)
  const formatLakhs = (val: number) => {
    const lakhs = val / 100000;
    return `₹ ${lakhs.toFixed(2)}L`;
  };

  const hasData = totalOutstanding > 0;
  const chartData = hasData ? data : [{ name: "No Outstanding", value: 1 }];

  return (
    <div className="bg-white p-4 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-slate-800 text-base">Collections Overview</h3>
          </div>
          <p className="text-[10px] text-slate-400 font-semibold mt-0.5">Current Portfolio Snapshot</p>
        </div>
        {viewReportHref ? (
          <Link href={viewReportHref} className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View report</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        ) : (
          <button className="text-xs font-semibold text-brand-blue hover:text-brand-blueHover hover:underline flex items-center gap-1">
            <span>View report</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row lg:flex-col xl:flex-row items-center justify-between gap-4 py-1">
        {/* Donut Chart with Centered Total */}
        <div className="relative w-36 h-36 flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={66}
                paddingAngle={hasData ? 3 : 0}
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={hasData ? COLORS[index % COLORS.length] : "#e2e8f0"} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          
          {/* Centered label */}
          <div className="absolute text-center flex flex-col items-center">
            <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Total Outstanding</span>
            <span className="text-sm font-extrabold text-slate-800 tracking-tight mt-0.5">
              {formatLakhs(totalOutstanding)}
            </span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex-1 space-y-2 w-full">
          {data.map((item, index) => (
            <div key={item.name} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span className="text-slate-600 font-semibold">{item.name}</span>
              </div>
              <span className="font-bold text-slate-800">
                {formatLakhs(item.value)} <span className="text-[10px] text-slate-400 font-normal">({item.percentage}%)</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Warnings Card */}
      <div className="mt-3 p-2.5 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between text-[11px] gap-2">
        <div className="flex items-center gap-2 text-amber-800">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span className="font-semibold">{overdue60Count ?? 12} customers have outstanding balances &gt; 60 days</span>
        </div>
        <Link href="/dashboard/customers?filter=overdue_60" className="text-brand-blue hover:text-brand-blueHover font-bold shrink-0 hover:underline">
          View customers
        </Link>
      </div>
    </div>
  );
}
