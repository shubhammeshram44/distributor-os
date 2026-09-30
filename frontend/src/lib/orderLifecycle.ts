import {
  OrderLifecycle,
  LifecycleStage,
  OrderProgress,
  OperationalException,
  OrderHoverPreviewData,
  PreviewStage,
  PreviewException,
  PreviewOwner,
  PreviewNextAction,
  PreviewContextItem,
  StageStatus,
} from "@/types/order";

/**
 * Default standard lifecycle for DistroOS orders.
 * In the future, this can be loaded per-tenant from the backend,
 * while the UI components consume this exact same interface.
 */
export const DEFAULT_ORDER_LIFECYCLE: OrderLifecycle = {
  id: "default_distribution_lifecycle",
  name: "Standard Distribution Lifecycle",
  stages: [
    {
      id: "received",
      name: "Received",
      sequence: 1,
      shortName: "REC",
      description: "Order captured via WhatsApp or Portal",
    },
    {
      id: "review",
      name: "Review",
      sequence: 2,
      shortName: "REV",
      description: "SKU mapping and inventory allocation review",
    },
    {
      id: "confirmed",
      name: "Confirmed",
      sequence: 3,
      shortName: "CNF",
      description: "Order confirmed and invoice ready for dispatch",
    },
    {
      id: "dispatched",
      name: "Dispatched",
      sequence: 4,
      shortName: "DSP",
      description: "Order dispatched with carrier or van",
    },
    {
      id: "delivered",
      name: "Delivered",
      sequence: 5,
      shortName: "DLV",
      description: "Order successfully delivered to retailer",
    },
  ],
};

export interface AdaptedOrderLifecycle {
  progress: OrderProgress;
  currentStage: LifecycleStage | undefined;
  exception: OperationalException | null;
  isCancelled: boolean;
  totalStages: number;
  currentStageIndex: number;
}

/**
 * Lifecycle Adapter
 * Bridges existing Order models / API responses into the generic OrderLifecycle domain.
 * When the backend supports tenant-customized lifecycles, this adapter seamlessly
 * prioritizes API-provided lifecycle definitions while falling back cleanly.
 */
export function adaptOrderToLifecycle(
  order: any,
  lifecycle: OrderLifecycle = DEFAULT_ORDER_LIFECYCLE
): AdaptedOrderLifecycle {
  const isCancelled =
    order.status === "Cancelled" ||
    order.status?.toLowerCase() === "cancelled";

  // If order already has a rich lifecycle from backend, use it directly
  if (order.lifecycle && order.lifecycle.currentStageId) {
    const stage = lifecycle.stages.find(
      (s) => s.id === order.lifecycle.currentStageId
    );
    const stageIndex = lifecycle.stages.findIndex(
      (s) => s.id === order.lifecycle.currentStageId
    );
    return {
      progress: order.lifecycle,
      currentStage: stage,
      exception: order.exception || null,
      isCancelled,
      totalStages: lifecycle.stages.length,
      currentStageIndex: stageIndex >= 0 ? stageIndex : 0,
    };
  }

  // Derive from existing order fields
  const lineItems = order.line_items || [];
  const hasUnmatchedSku = lineItems.some(
    (i: any) =>
      i.sku_id === "UNMATCHED_SKU" ||
      i.sku_id === "UNMATCHED_TRIAGE_SKU" ||
      !i.product_id
  );

  const totalRequested = lineItems.reduce(
    (sum: number, i: any) => sum + (i.quantity || 0),
    0
  );
  const totalAllocated = lineItems.reduce(
    (sum: number, i: any) =>
      sum +
      (i.allocated_quantity !== null && i.allocated_quantity !== undefined
        ? i.allocated_quantity
        : i.quantity || 0),
    0
  );
  const hasShortfall = totalAllocated < totalRequested;

  let ageHours = 0;
  if (order.created_on) {
    const createdTime = new Date(order.created_on).getTime();
    if (!isNaN(createdTime)) {
      ageHours = (Date.now() - createdTime) / (1000 * 60 * 60);
    }
  }

  let currentStageId = "received";
  let completedStageIds: string[] = [];
  let exception: OperationalException | null = null;

  if (isCancelled) {
    currentStageId = "received";
    completedStageIds = [];
    exception = {
      severity: "none",
      label: "Cancelled",
      actionHint: "Order cancelled",
    };
  } else {
    const status = order.status || "Draft";

    if (status === "Draft" || status === "Pending") {
      if (hasUnmatchedSku) {
        currentStageId = "review";
        completedStageIds = ["received"];
        exception = {
          severity: "warning",
          label: "Unmatched SKU",
          actionHint: "Map SKU in Details",
          suggestedAction: "review",
        };
      } else if (hasShortfall) {
        currentStageId = "review";
        completedStageIds = ["received"];
        exception = {
          severity: "warning",
          label: `Shortfall (${totalAllocated}/${totalRequested})`,
          actionHint: "Stock allocation shortfall",
          suggestedAction: "confirm",
        };
      } else if (ageHours >= 24) {
        currentStageId = "received";
        completedStageIds = [];
        exception = {
          severity: "info",
          label: `Pending ${Math.round(ageHours)}h`,
          actionHint: "Awaiting confirmation",
          suggestedAction: "confirm",
        };
      } else {
        currentStageId = "received";
        completedStageIds = [];
      }
    } else if (
      status === "Needs Review" ||
      status === "pending_review" ||
      status === "NEEDS_REVIEW"
    ) {
      currentStageId = "review";
      completedStageIds = ["received"];
      exception = {
        severity: "warning",
        label: hasUnmatchedSku ? "Unmatched SKU" : "Needs Review",
        actionHint: "Resolution required",
        suggestedAction: "review",
      };
    } else if (status === "Confirmed") {
      currentStageId = "confirmed";
      completedStageIds = ["received", "review"];
      if (hasShortfall) {
        exception = {
          severity: "warning",
          label: `Shortfall (${totalAllocated}/${totalRequested} alloc.)`,
          actionHint: "Partial stock allocation",
          suggestedAction: "invoice",
        };
      }
    } else if (status === "Dispatched") {
      currentStageId = "dispatched";
      completedStageIds = ["received", "review", "confirmed"];
    } else if (status === "Delivered") {
      currentStageId = "delivered";
      completedStageIds = [
        "received",
        "review",
        "confirmed",
        "dispatched",
        "delivered",
      ];
    } else {
      // Graceful fallback for unknown status
      currentStageId = lifecycle.stages[0]?.id || "received";
      completedStageIds = [];
    }
  }

  const currentStage = lifecycle.stages.find((s) => s.id === currentStageId);
  const currentStageIndex = lifecycle.stages.findIndex(
    (s) => s.id === currentStageId
  );

  return {
    progress: {
      lifecycleId: lifecycle.id,
      currentStageId,
      completedStageIds,
    },
    currentStage,
    exception,
    isCancelled,
    totalStages: lifecycle.stages.length,
    currentStageIndex: currentStageIndex >= 0 ? currentStageIndex : 0,
  };
}

function formatCurrencyINR(val: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);
}

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return "Just now";
  const time = new Date(dateStr).getTime();
  if (isNaN(time)) return "Just now";
  const diffSec = Math.max(0, (Date.now() - time) / 1000);
  if (diffSec < 60) return "Just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

/**
 * Derives rich, contextual OrderHoverPreviewData from an Order.
 * Consumes the generic OrderLifecycle domain model so tenant-specific lifecycle
 * rules from the backend can easily plug in without changing any UI presentation code.
 */
export function getOrderHoverPreview(
  order: any,
  lifecycle: OrderLifecycle = DEFAULT_ORDER_LIFECYCLE
): OrderHoverPreviewData {
  // If backend or future tenant runtime already supplied preview data, respect it directly
  if (order.hover_preview || order.preview) {
    return order.hover_preview || order.preview;
  }

  const adapted = adaptOrderToLifecycle(order, lifecycle);
  const { progress, currentStage, exception: basicException, isCancelled } = adapted;

  const lineItems = order.line_items || [];
  const totalRequested = lineItems.reduce(
    (sum: number, i: any) => sum + (i.quantity || 0),
    0
  );
  const totalAllocated = lineItems.reduce(
    (sum: number, i: any) =>
      sum +
      (i.allocated_quantity !== null && i.allocated_quantity !== undefined
        ? i.allocated_quantity
        : i.quantity || 0),
    0
  );
  const shortfallUnits = Math.max(0, totalRequested - totalAllocated);
  const hasShortfall = shortfallUnits > 0;
  const fulfillmentRate =
    totalRequested > 0 ? Math.round((totalAllocated / totalRequested) * 100) : 100;

  const unmatchedItems = lineItems.filter(
    (i: any) =>
      i.sku_id === "UNMATCHED_SKU" ||
      i.sku_id === "UNMATCHED_TRIAGE_SKU" ||
      !i.product_id
  );
  const hasUnmatchedSku = unmatchedItems.length > 0;

  let ageHours = 0;
  if (order.created_on) {
    const t = new Date(order.created_on).getTime();
    if (!isNaN(t)) {
      ageHours = Math.max(0, (Date.now() - t) / (1000 * 60 * 60));
    }
  }

  const status = order.status || "Draft";
  const relativeAge = formatRelativeTime(order.created_on);
  const totalAmount = order.amount || 0;
  const amountPaid = order.amount_paid || 0;
  const outstandingBalance = Math.max(0, totalAmount - amountPaid);

  let stageStatus: StageStatus = "on_track";
  if (isCancelled) {
    stageStatus = "blocked";
  } else if (status === "Delivered") {
    stageStatus = "completed";
  } else if (
    hasUnmatchedSku ||
    hasShortfall ||
    (status in ["Pending", "Draft"] && ageHours >= 24)
  ) {
    stageStatus = "attention";
  }

  const previewStage: PreviewStage = {
    id: currentStage?.id || "received",
    name: isCancelled ? "Cancelled" : currentStage?.name || "Processing",
    sequence: currentStage?.sequence || 1,
    status: stageStatus,
    shortName: currentStage?.shortName,
    description: currentStage?.description,
  };

  let exception: PreviewException | undefined = undefined;
  let owner: PreviewOwner | undefined = undefined;
  let explanation = "";
  let relevantContext: PreviewContextItem[] = [];
  let nextAction: PreviewNextAction | undefined = undefined;

  if (isCancelled) {
    owner = { role: "Order Admin", name: "Operations" };
    exception = {
      type: "cancelled",
      severity: "critical",
      title: "Order Cancelled",
      description: "Order processing stopped.",
      age: relativeAge,
    };
    explanation = "This order was cancelled. Inventory allocations were released back to stock.";
    relevantContext = [
      { label: "Order ID", value: order.order_id || "-" },
      { label: "Total Value", value: formatCurrencyINR(totalAmount) },
      { label: "Channel", value: order.channel || "WhatsApp" },
      { label: "Status", value: "Cancelled" },
    ];
    nextAction = {
      label: "View Audit Trail",
      description: "Inspect timeline, cancellations, and order logs.",
      action: "details",
      enabled: true,
    };
  } else if (hasUnmatchedSku) {
    owner = { role: "Catalog Manager", name: "Operations" };
    exception = {
      type: "unmatched_sku",
      severity: "warning",
      title: `Unmatched SKU (${unmatchedItems.length})`,
      description: "Items requiring catalog resolution.",
      age: relativeAge,
    };
    explanation = `${unmatchedItems.length} ${
      unmatchedItems.length === 1 ? "item" : "items"
    } received via ${order.channel || "WhatsApp"} could not be mapped to catalog SKUs.`;
    relevantContext = [
      {
        label: "Unmapped SKUs",
        value: `${unmatchedItems.length} of ${lineItems.length} line items`,
      },
      { label: "Order Channel", value: order.channel || "WhatsApp" },
      { label: "Captured", value: relativeAge },
      { label: "Order Value", value: formatCurrencyINR(totalAmount) },
    ];
    nextAction = {
      label: "Review & Map SKUs",
      description: "Map unmapped items to catalog products in Order Details.",
      action: "review",
      enabled: true,
    };
  } else if (hasShortfall) {
    owner = { role: "Inventory Dispatcher", name: "Warehouse" };
    exception = {
      type: "stock_shortfall",
      severity: "warning",
      title: `Stock Shortfall (${totalAllocated}/${totalRequested})`,
      description: "Stock shortage for full order.",
      age: relativeAge,
    };
    explanation = `Requested units (${totalRequested}) exceed available warehouse stock (${totalAllocated}). ${shortfallUnits} units unallocated.`;
    relevantContext = [
      { label: "Allocated Units", value: `${totalAllocated} / ${totalRequested}` },
      { label: "Fulfillment Rate", value: `${fulfillmentRate}%` },
      { label: "Shortfall Gap", value: `${shortfallUnits} units` },
      { label: "Order Value", value: formatCurrencyINR(totalAmount) },
    ];
    nextAction =
      status === "Confirmed"
        ? {
            label: "Download Invoice",
            description: "Print B2B invoice with allocated stock for dispatch.",
            action: "invoice",
            enabled: true,
          }
        : {
            label: "Confirm Partial Allocation",
            description: "Proceed with partial stock or wait for replenishment.",
            action: "confirm",
            enabled: true,
          };
  } else if (ageHours >= 24 && (status === "Draft" || status === "Pending")) {
    owner = { role: "Sales Manager", name: "Dispatcher" };
    exception = {
      type: "pending_sla",
      severity: "info",
      title: `Pending Confirmation (${Math.round(ageHours)}h)`,
      description: "Order awaiting approval over 24 hours.",
      age: relativeAge,
    };
    explanation = `Order captured ${Math.round(
      ageHours
    )} hours ago and has not yet been confirmed for fulfillment.`;
    relevantContext = [
      { label: "Order Age", value: `${Math.round(ageHours)} hours` },
      {
        label: "Units to Pack",
        value: `${totalAllocated} units (${lineItems.length} items)`,
      },
      { label: "Channel", value: order.channel || "WhatsApp" },
      { label: "Order Value", value: formatCurrencyINR(totalAmount) },
    ];
    nextAction = {
      label: "Review & Confirm Order",
      description: "Confirm inventory allocations to generate invoice.",
      action: "confirm",
      enabled: true,
    };
  } else if (status === "Draft" || status === "Pending") {
    owner = { role: "Sales Manager", name: "Dispatcher" };
    explanation = "Order received from retailer. Stock is allocated and awaiting confirmation.";
    relevantContext = [
      {
        label: "Units to Pack",
        value: `${totalAllocated} units (${lineItems.length} items)`,
      },
      { label: "Fulfillment Rate", value: "100%" },
      { label: "Channel", value: order.channel || "WhatsApp" },
      { label: "Received", value: relativeAge },
    ];
    nextAction = {
      label: "Confirm Order",
      description: "Lock allocations and generate B2B invoice.",
      action: "confirm",
      enabled: true,
    };
  } else if (status === "Confirmed") {
    owner = { role: "Warehouse & Logistics", name: "Dispatcher" };
    explanation = "Order confirmed and invoice ready. Awaiting vehicle loading and dispatch.";
    relevantContext = [
      {
        label: "Invoice Type",
        value:
          order.invoice_type === "GST_TAX_INVOICE"
            ? "GST Tax Invoice"
            : order.invoice_type || "Standard Invoice",
      },
      { label: "Packed Units", value: `${totalAllocated} units` },
      {
        label: "Payment Status",
        value:
          order.payment_status === "PAID"
            ? "Paid"
            : order.payment_status === "PARTIALLY_PAID"
            ? "Partial"
            : "Unpaid",
      },
      { label: "Retailer", value: order.customer || "-" },
    ];
    nextAction = {
      label: "Download Invoice",
      description: "Print B2B invoice copy for delivery van loading.",
      action: "invoice",
      enabled: true,
    };
  } else if (status === "Dispatched") {
    owner = { role: "Delivery Personnel", name: "Van Driver" };
    explanation = "Order dispatched with delivery personnel. En route to retailer store.";
    relevantContext = [
      { label: "Delivery Mode", value: "Van Sales / Direct Carrier" },
      { label: "Dispatched", value: relativeAge },
      { label: "Destination", value: order.customer || "-" },
      { label: "Invoice Amount", value: formatCurrencyINR(totalAmount) },
    ];
    nextAction = {
      label: "Record Delivery",
      description: "Record proof of delivery and timestamp in Order Details.",
      action: "deliver",
      enabled: true,
    };
  } else if (status === "Delivered") {
    if (order.payment_status !== "PAID") {
      owner = { role: "Collections Agent", name: "Accounts" };
      exception = {
        type: "payment_pending",
        severity: "info",
        title: `Payment Pending (${formatCurrencyINR(outstandingBalance)})`,
        description: "Delivered order awaiting collection.",
        age: relativeAge,
      };
      explanation = `Order delivered to retailer. Outstanding balance of ${formatCurrencyINR(
        outstandingBalance
      )} is pending collection.`;
      relevantContext = [
        { label: "Delivered To", value: order.customer || "-" },
        { label: "Total Amount", value: formatCurrencyINR(totalAmount) },
        { label: "Amount Paid", value: formatCurrencyINR(amountPaid) },
        { label: "Outstanding Due", value: formatCurrencyINR(outstandingBalance) },
      ];
      nextAction = {
        label: "Collect Payment",
        description: "Record payment collection in Order Details.",
        action: "details",
        enabled: true,
      };
    } else {
      owner = { role: "Fulfillment Team", name: "Completed" };
      explanation = "Order successfully fulfilled and payment settled in full.";
      relevantContext = [
        { label: "Delivered To", value: order.customer || "-" },
        { label: "Total Paid", value: formatCurrencyINR(totalAmount) },
        { label: "Payment Status", value: "Fully Paid" },
        { label: "Fulfillment", value: "Complete" },
      ];
      nextAction = {
        label: "View Receipt & Audit",
        description: "View financial ledger and delivery audit trail.",
        action: "details",
        enabled: true,
      };
    }
  } else {
    // Graceful default fallback for any unmapped status
    owner = { role: "Operations", name: "Dispatcher" };
    explanation = `Order is in ${status} status.`;
    relevantContext = [
      { label: "Retailer", value: order.customer || "-" },
      { label: "Order Value", value: formatCurrencyINR(totalAmount) },
      { label: "Status", value: status },
      { label: "Channel", value: order.channel || "Portal" },
    ];
    nextAction = {
      label: "View Order Details",
      description: "Inspect line items, financial summary, and history.",
      action: "details",
      enabled: true,
    };
  }

  return {
    orderId: order.id,
    internalId: order.order_id || "-",
    customer: order.customer || "Unknown Retailer",
    amount: totalAmount,
    channel: order.channel || "WhatsApp",
    createdOn: order.created_on || new Date().toISOString(),
    paymentStatus: order.payment_status || "UNPAID",
    amountPaid: amountPaid,
    currentStage: previewStage,
    exception,
    owner,
    explanation,
    relevantContext,
    nextAction,
    lifecycle: {
      stages: lifecycle.stages,
      currentStageId: progress.currentStageId,
      completedStageIds: progress.completedStageIds,
    },
    isCancelled,
  };
}
