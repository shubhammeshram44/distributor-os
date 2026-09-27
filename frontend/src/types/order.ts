export const InvoiceTypes = {
  GST: "GST_TAX_INVOICE",
  RETAIL: "RETAIL_INVOICE",
  UNSPECIFIED: "UNSPECIFIED"
} as const;

export type InvoiceType = typeof InvoiceTypes[keyof typeof InvoiceTypes];

export interface LifecycleStage {
  id: string;
  name: string;
  sequence: number;
  shortName?: string;
  description?: string;
}

export interface OrderLifecycle {
  id: string;
  name: string;
  stages: LifecycleStage[];
}

export interface OrderProgress {
  lifecycleId: string;
  currentStageId: string;
  completedStageIds: string[];
}

export type ExceptionSeverity = "warning" | "error" | "info" | "none";

export interface OperationalException {
  severity: ExceptionSeverity;
  label: string;
  actionHint?: string;
  suggestedAction?: "confirm" | "deliver" | "invoice" | "review" | "details";
}

export interface Order {
  id: string;
  order_id: string;
  customer: string;
  channel: string;
  amount: number;
  status: string;
  created_on: string;
  eta: string;
  payment_status: string;
  amount_paid: number;
  invoice_type: InvoiceType;
  raw_source_text?: string;
  lifecycle?: OrderProgress;
  exception?: OperationalException;
}

export interface OrderLineItem {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
  allocated_quantity: number | null;
  unit_price: number;
  total_price: number;
  raw_source_text?: string;
  product_id?: string | null;
}
