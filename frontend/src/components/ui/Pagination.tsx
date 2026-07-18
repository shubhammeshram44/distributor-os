"use client";

import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  total: number;
  skip: number;
  limit: number;
  onPageChange: (newSkip: number) => void;
}

export default function Pagination({ total, skip, limit, onPageChange }: PaginationProps) {
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  const start = skip + 1;
  const end = Math.min(skip + limit, total);

  return (
    <div className="flex items-center justify-between px-1 py-2">
      <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
        Showing {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(Math.max(0, skip - limit))}
          disabled={skip === 0}
          className="w-8 h-8 flex items-center justify-center rounded-lg border border-dashboard-border text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:border-brand-blue hover:text-brand-blue transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
          // Show pages around current page
          let pageNum: number;
          if (totalPages <= 5) {
            pageNum = i + 1;
          } else if (currentPage <= 3) {
            pageNum = i + 1;
          } else if (currentPage >= totalPages - 2) {
            pageNum = totalPages - 4 + i;
          } else {
            pageNum = currentPage - 2 + i;
          }

          const isActive = pageNum === currentPage;
          return (
            <button
              key={pageNum}
              onClick={() => onPageChange((pageNum - 1) * limit)}
              className={`w-8 h-8 flex items-center justify-center rounded-lg text-xs font-semibold transition-all ${isActive
                  ? "bg-brand-blue text-white border border-brand-blue"
                  : "border border-dashboard-border text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:border-brand-blue hover:text-brand-blue"
                }`}
              aria-label={`Page ${pageNum}`}
              aria-current={isActive ? "page" : undefined}
            >
              {pageNum}
            </button>
          );
        })}

        <button
          onClick={() => onPageChange(skip + limit)}
          disabled={skip + limit >= total}
          className="w-8 h-8 flex items-center justify-center rounded-lg border border-dashboard-border text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5 hover:border-brand-blue hover:text-brand-blue transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
