"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  SlidersHorizontal,
  RotateCcw,
  Check,
  Lock,
  ArrowUp,
  ArrowDown,
  Search,
  X,
} from "lucide-react";
import { TableColumnDefinition, ColumnId } from "@/types/table";

interface ManageColumnsPopoverProps<TRow = any> {
  allColumns: TableColumnDefinition<TRow>[];
  orderedColumns: TableColumnDefinition<TRow>[];
  visibleColumnIds: Set<ColumnId>;
  isCustom: boolean;
  requiredColumns?: ColumnId[];
  onToggleColumn: (colId: ColumnId) => void;
  onMoveColumn: (colId: ColumnId, direction: "up" | "down") => void;
  onResetToDefault: () => void;
  isSaving?: boolean;
}

export default function ManageColumnsPopover<TRow = any>({
  allColumns,
  orderedColumns,
  visibleColumnIds,
  isCustom,
  requiredColumns = [],
  onToggleColumn,
  onMoveColumn,
  onResetToDefault,
  isSaving = false,
}: ManageColumnsPopoverProps<TRow>) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const visibleCount = visibleColumnIds.size;
  const totalCount = allColumns.length;

  const filteredColumns = orderedColumns.filter((col) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return (
      col.label.toLowerCase().includes(term) ||
      (col.description && col.description.toLowerCase().includes(term))
    );
  });

  return (
    <div className="relative inline-block text-left">
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`px-3 py-2 border rounded-lg text-xs font-bold transition-all flex items-center gap-2 cursor-pointer shadow-sm ${
          isOpen || isCustom
            ? "border-brand-blue/50 text-brand-blue bg-brand-blue/5 dark:bg-brand-blue/10"
            : "border-dashboard-border text-slate-700 dark:text-slate-200 bg-white dark:bg-dashboard-card hover:bg-slate-50 dark:hover:bg-white/5"
        }`}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        title="Manage visible table columns and sequence"
      >
        <SlidersHorizontal className="w-3.5 h-3.5" />
        <span>Columns</span>
        <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-slate-300 font-extrabold">
          {visibleCount}/{totalCount}
        </span>
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label="Manage table columns"
          className="absolute right-0 mt-2 w-84 bg-white dark:bg-dashboard-card border border-dashboard-border rounded-xl shadow-xl z-40 overflow-hidden animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Header */}
          <div className="p-3 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 dark:bg-white/[0.02]">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-extrabold text-slate-800 dark:text-slate-100">
                  Manage Columns
                </h4>
                {isCustom && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-blue-50 dark:bg-blue-500/10 text-brand-blue border border-brand-blue/20">
                    Custom
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Toggle visibility and order of columns
              </p>
            </div>

            <button
              type="button"
              onClick={onResetToDefault}
              disabled={!isCustom}
              className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded transition-colors ${
                isCustom
                  ? "text-brand-blue hover:bg-brand-blue/10 cursor-pointer"
                  : "text-slate-400 dark:text-slate-600 cursor-not-allowed"
              }`}
              title="Reset columns to product defaults"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset</span>
            </button>
          </div>

          {/* Search Filter */}
          <div className="p-2 border-b border-dashboard-border">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Find column..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-7 py-1 text-xs border border-dashboard-border rounded-md bg-white dark:bg-dashboard-inset focus:outline-none focus:ring-1 focus:ring-brand-blue text-slate-800 dark:text-slate-200 placeholder-slate-400"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

          {/* Column List */}
          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 dark:divide-white/5 p-1">
            {filteredColumns.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-400">
                No matching columns found
              </div>
            ) : (
              filteredColumns.map((col, index) => {
                const isVisible = visibleColumnIds.has(col.id);
                const isRequired =
                  col.required || requiredColumns.includes(col.id);
                const isFirst = index === 0;
                const isLast = index === filteredColumns.length - 1;

                return (
                  <div
                    key={col.id}
                    className={`flex items-center justify-between p-2 rounded-lg transition-colors group ${
                      isVisible
                        ? "hover:bg-slate-50 dark:hover:bg-white/5"
                        : "opacity-60 hover:opacity-100 hover:bg-slate-50 dark:hover:bg-white/5"
                    }`}
                  >
                    {/* Toggle Checkbox and Label */}
                    <label
                      className={`flex items-center gap-2.5 flex-1 min-w-0 ${
                        isRequired ? "cursor-not-allowed" : "cursor-pointer"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isVisible}
                        disabled={isRequired}
                        onChange={() => onToggleColumn(col.id)}
                        className={`w-3.5 h-3.5 rounded border-slate-300 dark:border-white/20 text-brand-blue focus:ring-brand-blue focus:ring-offset-0 ${
                          isRequired ? "cursor-not-allowed opacity-70" : "cursor-pointer"
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-xs font-semibold truncate ${
                              isVisible
                                ? "text-slate-800 dark:text-slate-200"
                                : "text-slate-500 dark:text-slate-400"
                            }`}
                          >
                            {col.label}
                          </span>
                          {isRequired && (
                            <span
                              className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[9px] font-bold bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20"
                              title="Primary column cannot be removed"
                            >
                              <Lock className="w-2.5 h-2.5" />
                              Required
                            </span>
                          )}
                        </div>
                        {col.description && (
                          <p className="text-[10px] text-slate-400 truncate">
                            {col.description}
                          </p>
                        )}
                      </div>
                    </label>

                    {/* Reorder Buttons */}
                    <div className="flex items-center gap-0.5 pl-2 opacity-60 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => onMoveColumn(col.id, "up")}
                        disabled={isFirst}
                        className={`p-1 rounded transition-colors ${
                          isFirst
                            ? "text-slate-200 dark:text-white/10 cursor-not-allowed"
                            : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/10 cursor-pointer"
                        }`}
                        title="Move column up"
                        aria-label={`Move ${col.label} up`}
                      >
                        <ArrowUp className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onMoveColumn(col.id, "down")}
                        disabled={isLast}
                        className={`p-1 rounded transition-colors ${
                          isLast
                            ? "text-slate-200 dark:text-white/10 cursor-not-allowed"
                            : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/10 cursor-pointer"
                        }`}
                        title="Move column down"
                        aria-label={`Move ${col.label} down`}
                      >
                        <ArrowDown className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="p-2.5 border-t border-dashboard-border bg-slate-50/50 dark:bg-white/[0.02] flex items-center justify-between text-[11px]">
            <span className="text-slate-400">
              {isSaving ? "Saving preference..." : "Preferences saved"}
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="px-3 py-1 bg-brand-blue hover:bg-brand-blueHover text-white font-bold rounded-lg transition-colors cursor-pointer"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
