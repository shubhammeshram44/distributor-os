export const InvoiceTypes = {
  GST: "GST_TAX_INVOICE",
  RETAIL: "RETAIL_INVOICE",
  UNSPECIFIED: "UNSPECIFIED"
} as const;

export type InvoiceType = typeof InvoiceTypes[keyof typeof InvoiceTypes];

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
}
