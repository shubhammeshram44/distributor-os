"use client";

import React from "react";
import { MessageSquare, Globe, AlertTriangle, CheckCircle, Package } from "lucide-react";
import { TableDefinition, TableColumnDefinition } from "@/types/table";
import { InvoiceTypes, InvoiceType } from "@/types/order";
import { formatDateTime } from "@/utils/datetime";
import OrderLifecycleProgress from "@/components/orders/OrderLifecycleProgress";
import OrderCurrentStage from "@/components/orders/OrderCurrentStage";
import { adaptOrderToLifecycle, DEFAULT_ORDER_LIFECYCLE } from "@/lib/orderLifecycle";

export interface OrderRowContext {
  onOrderIdClick: (order: any) => void;
  onTriggerMouseEnter?: (
    e: React.MouseEvent<HTMLElement> | React.FocusEvent<HTMLElement>,
    order: any
  ) => void;
  onTriggerMouseLeave?: () => void;
  formatCurrency: (amount: number) => string;
}

export function renderInvoiceTypeBadge(type: InvoiceType) {
  switch (type) {
    case InvoiceTypes.GST:
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-[11px] font-bold leading-none bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20 shadow-2xs whitespace-nowrap">
          GST Bill
        </span>
      );
    case InvoiceTypes.RETAIL:
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-[11px] font-bold leading-none bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20 shadow-2xs whitespace-nowrap">
          Retail Bill
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-[11px] font-bold leading-none bg-slate-50 dark:bg-dashboard-inset text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-white/10 shadow-2xs whitespace-nowrap">
          Unspecified
        </span>
      );
  }
}

/**
 * Concrete TableDefinition for DistroOS Orders
 * Version 1
 */
export const ORDERS_TABLE_DEFINITION: TableDefinition<any> = {
  pageKey: "orders",
  version: 1,
  requiredColumns: ["order"],
  defaultColumnOrder: [
    "order",
    "customer",
    "lifecycle",
    "issue_action",
    "amount",
    "payment",
    "created_at",
  ],
  columns: [
    // 1. Order ID (Required, pinned)
    {
      id: "order",
      label: "Order",
      description: "Order reference number and quick preview trigger",
      supported: true,
      defaultVisible: true,
      required: true,
      align: "left",
      minWidth: "120px",
      renderCell: (order, ctx: OrderRowContext) => (
        <div
          className="inline-flex items-center gap-1.5 cursor-pointer"
          onMouseEnter={(e) => ctx.onTriggerMouseEnter?.(e, order)}
          onMouseLeave={() => ctx.onTriggerMouseLeave?.()}
          onFocus={(e) => ctx.onTriggerMouseEnter?.(e, order)}
          onBlur={() => ctx.onTriggerMouseLeave?.()}
        >
          <button
            onClick={() => ctx.onOrderIdClick(order)}
            className="cursor-pointer font-bold text-left text-brand-blue hover:underline focus:outline-none focus:ring-1 focus:ring-brand-blue rounded"
            aria-haspopup="dialog"
            aria-label={`Order ${order.order_id}, click for details, hover for preview`}
          >
            {order.order_id}
          </button>
        </div>
      ),
    },

    // 2. Customer
    {
      id: "customer",
      label: "Customer",
      description: "Retailer / store name",
      supported: true,
      defaultVisible: true,
      align: "left",
      minWidth: "160px",
      renderCell: (order) => (
        <span
          className="font-semibold text-slate-700 dark:text-slate-300 max-w-[180px] truncate block"
          title={order.customer}
        >
          {order.customer || "—"}
        </span>
      ),
    },

    // 3. Lifecycle Progress
    {
      id: "lifecycle",
      label: "Lifecycle",
      description: "Operational journey progress bar",
      supported: true,
      defaultVisible: true,
      align: "left",
      minWidth: "130px",
      renderCell: (order) => {
        const { progress, isCancelled } = adaptOrderToLifecycle(
          order,
          DEFAULT_ORDER_LIFECYCLE
        );
        return (
          <OrderLifecycleProgress
            stages={DEFAULT_ORDER_LIFECYCLE.stages}
            currentStageId={progress.currentStageId}
            completedStageIds={progress.completedStageIds}
            isCancelled={isCancelled}
          />
        );
      },
    },

    // 4. Current Issue / Next Action
    {
      id: "issue_action",
      label: "Current Issue / Next Action",
      description: "Operational stage badge and exception context",
      supported: true,
      defaultVisible: true,
      align: "left",
      minWidth: "140px",
      renderCell: (order) => {
        const { currentStage, exception, isCancelled } = adaptOrderToLifecycle(
          order,
          DEFAULT_ORDER_LIFECYCLE
        );
        return (
          <OrderCurrentStage
            stage={currentStage}
            exception={exception}
            isCancelled={isCancelled}
          />
        );
      },
    },

    // 5. Amount
    {
      id: "amount",
      label: "Amount",
      description: "Total invoice value",
      supported: true,
      defaultVisible: true,
      align: "right",
      minWidth: "100px",
      renderCell: (order, ctx: OrderRowContext) => (
        <span className="font-extrabold text-slate-800 dark:text-slate-100 whitespace-nowrap">
          {ctx.formatCurrency(order.amount || 0)}
        </span>
      ),
    },

    // 6. Payment
    {
      id: "payment",
      label: "Payment",
      description: "Payment collection status",
      supported: true,
      defaultVisible: true,
      align: "center",
      minWidth: "110px",
      renderCell: (order) => {
        const status = order.payment_status;
        const isPaid = status === "PAID";
        const isPartial = status === "PARTIALLY_PAID";

        return (
          <span
            className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-full text-xs font-bold leading-none border ${
              isPaid
                ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20"
                : isPartial
                ? "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20"
                : "bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-500/20"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isPaid
                  ? "bg-emerald-500"
                  : isPartial
                  ? "bg-amber-500"
                  : "bg-rose-500"
              }`}
            />
            {isPaid ? "Paid" : isPartial ? "Partial" : "Unpaid"}
          </span>
        );
      },
    },

    // 7. Created On
    {
      id: "created_at",
      label: "Created On",
      description: "Date and time the order was placed",
      supported: true,
      defaultVisible: true,
      align: "left",
      minWidth: "130px",
      renderCell: (order) => (
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 whitespace-nowrap">
          {formatDateTime(order.created_on, "datetime")}
        </span>
      ),
    },

    // 8. Sales Channel (Optional)
    {
      id: "channel",
      label: "Channel",
      description: "Order intake platform (WhatsApp or Web Portal)",
      supported: true,
      defaultVisible: false,
      align: "center",
      minWidth: "80px",
      renderCell: (order) => {
        const isWa = String(order.channel || "").toLowerCase() === "whatsapp";
        return (
          <div className="flex items-center justify-center">
            {isWa ? (
              <div
                className="w-7 h-7 rounded-full bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shadow-2xs"
                title="WhatsApp Order"
              >
                <MessageSquare className="w-3.5 h-3.5" />
              </div>
            ) : (
              <div
                className="w-7 h-7 rounded-full bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400 shadow-2xs"
                title="Portal Order"
              >
                <Globe className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        );
      },
    },

    // 9. Invoice Type (Optional)
    {
      id: "invoice_type",
      label: "Invoice Type",
      description: "GST Tax Invoice vs Retail Cash Bill",
      supported: true,
      defaultVisible: false,
      align: "center",
      minWidth: "110px",
      renderCell: (order) => renderInvoiceTypeBadge(order.invoice_type),
    },

    // 10. Amount Paid (Optional)
    {
      id: "amount_paid",
      label: "Amount Paid",
      description: "Collected payment amount received against invoice",
      supported: true,
      defaultVisible: false,
      align: "right",
      minWidth: "100px",
      renderCell: (order, ctx: OrderRowContext) => (
        <span className="text-xs font-bold text-slate-700 dark:text-slate-300 whitespace-nowrap">
          {ctx.formatCurrency(order.amount_paid || 0)}
        </span>
      ),
    },

    // 11. ETA / Expected Delivery (Optional)
    {
      id: "eta",
      label: "ETA",
      description: "Expected dispatch and delivery date",
      supported: true,
      defaultVisible: false,
      align: "left",
      minWidth: "120px",
      renderCell: (order) => (
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 whitespace-nowrap">
          {order.eta ? formatDateTime(order.eta, "date") : "—"}
        </span>
      ),
    },

    // 12. Allocation Status (Optional)
    {
      id: "allocation",
      label: "Allocation",
      description: "Stock fulfillment coverage across line items",
      supported: true,
      defaultVisible: false,
      align: "left",
      minWidth: "130px",
      renderCell: (order) => {
        const lineItems = order.line_items || [];
        if (lineItems.length === 0) {
          return <span className="text-xs text-slate-400">—</span>;
        }

        const totalReq = lineItems.reduce(
          (sum: number, i: any) => sum + (i.quantity || 0),
          0
        );
        const totalAlloc = lineItems.reduce(
          (sum: number, i: any) =>
            sum +
            (i.allocated_quantity !== null && i.allocated_quantity !== undefined
              ? i.allocated_quantity
              : i.quantity || 0),
          0
        );
        const shortfall = Math.max(0, totalReq - totalAlloc);

        if (shortfall > 0) {
          return (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-500/20 whitespace-nowrap">
              <AlertTriangle className="w-3 h-3" />
              {totalAlloc}/{totalReq} units
            </span>
          );
        }

        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-500/20 whitespace-nowrap">
            <CheckCircle className="w-3 h-3" />
            Full ({totalAlloc} units)
          </span>
        );
      },
    },

    // 13. SKU Review State (Optional)
    {
      id: "sku_review",
      label: "SKU Review",
      description: "Line item product catalog resolution status",
      supported: true,
      defaultVisible: false,
      align: "left",
      minWidth: "130px",
      renderCell: (order) => {
        const lineItems = order.line_items || [];
        const unmatched = lineItems.filter(
          (i: any) =>
            i.sku_id === "UNMATCHED_SKU" ||
            i.sku_id === "UNMATCHED_TRIAGE_SKU" ||
            !i.product_id
        );

        if (unmatched.length > 0) {
          return (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-500/20 whitespace-nowrap">
              <AlertTriangle className="w-3 h-3" />
              {unmatched.length} Unmatched
            </span>
          );
        }

        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 dark:text-slate-400 whitespace-nowrap">
            <CheckCircle className="w-3 h-3 text-emerald-500" />
            All Matched
          </span>
        );
      },
    },

    // 14. Raw Source Text (Optional)
    {
      id: "source_message",
      label: "Source Message",
      description: "Original raw inbound text message",
      supported: true,
      defaultVisible: false,
      align: "left",
      minWidth: "150px",
      renderCell: (order) => {
        const raw = order.raw_source_text;
        if (!raw) return <span className="text-xs text-slate-400">—</span>;
        return (
          <span
            className="text-xs text-slate-600 dark:text-slate-400 italic block max-w-[200px] truncate"
            title={raw}
          >
            &ldquo;{raw}&rdquo;
          </span>
        );
      },
    },
  ],
};
