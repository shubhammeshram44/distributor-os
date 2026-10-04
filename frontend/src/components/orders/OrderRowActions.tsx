"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  MoreHorizontal,
  ChevronRight,
  Eye,
  Download,
  FileText,
  Copy,
  Ban,
  Tag,
} from "lucide-react";
import { getOrderPrimaryAction } from "@/lib/orderLifecycle";

interface OrderRowActionsProps {
  order: any;
  onOpenDetails: (order: any) => void;
  onDownloadInvoice: (order: any) => void;
  onChangeInvoiceType?: (order: any) => void;
  onCancelOrder?: (order: any) => void;
  onCopyOrderId?: (order: any) => void;
}

export default function OrderRowActions({
  order,
  onOpenDetails,
  onDownloadInvoice,
  onChangeInvoiceType,
  onCancelOrder,
  onCopyOrderId,
}: OrderRowActionsProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const primaryAction = getOrderPrimaryAction(order);
  const isCancelled =
    order.status === "Cancelled" ||
    String(order.status).toLowerCase() === "cancelled";
  const isDelivered =
    order.status === "Delivered" ||
    String(order.status).toLowerCase() === "delivered";

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
      }
    }
    if (isMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isMenuOpen]);

  // Can download invoice if order is confirmed/dispatched/delivered or invoice_id is present
  const canDownloadInvoice =
    Boolean(order.invoice_id) ||
    order.status === "Confirmed" ||
    order.status === "Partially Confirmed" ||
    order.status === "Dispatched" ||
    order.status === "Delivered";

  // Can cancel if not already cancelled and not delivered
  const canCancel = !isCancelled && !isDelivered;

  return (
    <div className="relative inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
      {/* 1. Primary Contextual Action */}
      {primaryAction === "deliver" && (
        <button
          type="button"
          onClick={() => onOpenDetails(order)}
          className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 dark:bg-teal-500/10 dark:hover:bg-teal-500/20 dark:text-teal-400 dark:border-teal-500/20 transition-all cursor-pointer shadow-2xs"
          title="Mark order as delivered"
        >
          Deliver
        </button>
      )}

      {primaryAction === "invoice" && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDownloadInvoice(order);
          }}
          className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 dark:bg-blue-500/10 dark:hover:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/20 transition-all cursor-pointer shadow-2xs"
          title="Download B2B Invoice"
        >
          Invoice
        </button>
      )}

      {primaryAction === "confirm" && (
        <button
          type="button"
          onClick={() => onOpenDetails(order)}
          className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/20 transition-all cursor-pointer shadow-2xs"
          title="Review & Confirm order"
        >
          Confirm
        </button>
      )}

      {primaryAction === "review" && (
        <button
          type="button"
          onClick={() => onOpenDetails(order)}
          className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:hover:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/20 transition-all cursor-pointer shadow-2xs"
          title="Review & map unmatched SKUs"
        >
          Review
        </button>
      )}

      {/* Details button (always accessible or default primary) */}
      <button
        type="button"
        onClick={() => onOpenDetails(order)}
        className="inline-flex items-center gap-0.5 text-xs font-bold text-brand-blue hover:text-brand-blueHover cursor-pointer py-1 px-1.5 rounded hover:bg-brand-blue/5 transition-all"
        title="Open order details drawer"
      >
        <span>Details</span>
        <ChevronRight className="w-3.5 h-3.5" />
      </button>

      {/* 2. Secondary Actions Overflow Menu Button */}
      <div className="relative">
        <button
          ref={buttonRef}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsMenuOpen((prev) => !prev);
          }}
          className={`p-1 rounded-md transition-colors ${
            isMenuOpen
              ? "bg-slate-200 dark:bg-white/10 text-slate-900 dark:text-white"
              : "text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 cursor-pointer"
          }`}
          title="More actions"
          aria-haspopup="menu"
          aria-expanded={isMenuOpen}
        >
          <MoreHorizontal className="w-4 h-4" />
        </button>

        {/* Dropdown Menu */}
        {isMenuOpen && (
          <div
            ref={menuRef}
            role="menu"
            className="absolute right-0 mt-1 w-48 bg-white dark:bg-dashboard-card border border-dashboard-border rounded-xl shadow-xl z-30 py-1 overflow-hidden animate-in fade-in zoom-in-95 duration-75 text-left"
          >
            {/* View Details */}
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setIsMenuOpen(false);
                onOpenDetails(order);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
            >
              <Eye className="w-3.5 h-3.5 text-slate-400" />
              <span>View Details</span>
            </button>

            {/* Download Invoice */}
            {canDownloadInvoice && (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  onDownloadInvoice(order);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-blue-500" />
                <span>Download Invoice</span>
              </button>
            )}

            {/* Change Invoice Type */}
            {onChangeInvoiceType && !isCancelled && !isDelivered && (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  onChangeInvoiceType(order);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
              >
                <Tag className="w-3.5 h-3.5 text-purple-500" />
                <span>Change Invoice Type</span>
              </button>
            )}

            {/* Copy Order ID */}
            {onCopyOrderId && (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  onCopyOrderId(order);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
              >
                <Copy className="w-3.5 h-3.5 text-slate-400" />
                <span>Copy Order ID</span>
              </button>
            )}

            {/* Cancel Order */}
            {canCancel && onCancelOrder && (
              <>
                <div className="my-1 border-t border-dashboard-border" />
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsMenuOpen(false);
                    onCancelOrder(order);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors cursor-pointer"
                >
                  <Ban className="w-3.5 h-3.5" />
                  <span>Cancel Order</span>
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
