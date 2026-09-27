import {
  OrderLifecycle,
  LifecycleStage,
  OrderProgress,
  OperationalException,
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
