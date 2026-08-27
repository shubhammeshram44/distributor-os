"use client";

import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";

export interface FulfillmentPreviewLine {
  item_id: string;
  product_id: string | null;
  requested_quantity: number;
  available_quantity: number;
  suggested_quantity: number;
  has_shortage: boolean;
}

export interface FulfillmentPreview {
  order_id: string;
  has_shortage: boolean;
  requested_quantity: number;
  available_quantity: number;
  suggested_quantity: number;
  lines: FulfillmentPreviewLine[];
}

interface Props {
  open: boolean;
  orderNumber: string;
  preview: FulfillmentPreview | null;
  submitting: boolean;
  onClose: () => void;
  onConfirmAvailable: () => void;
  onConfirmCustom: (quantities: Record<string, number>) => void;
  onCancelFull: () => void;
}

export default function FulfillmentDecisionModal({
  open,
  orderNumber,
  preview,
  submitting,
  onClose,
  onConfirmAvailable,
  onConfirmCustom,
  onCancelFull,
}: Props) {
  const [mode, setMode] = useState<"choice" | "custom">("choice");
  const [quantities, setQuantities] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!open || !preview) return;
    const initial: Record<string, number> = {};
    preview.lines.forEach((line) => {
      initial[line.item_id] = line.suggested_quantity;
    });
    setQuantities(initial);
    setMode("choice");
  }, [open, preview]);

  const confirmedTotal = useMemo(
    () => Object.values(quantities).reduce((sum, qty) => sum + (Number(qty) || 0), 0),
    [quantities]
  );

  if (!open || !preview) return null;

  const updateQty = (line: FulfillmentPreviewLine, raw: string) => {
    const parsed = Number(raw);
    const bounded = Number.isFinite(parsed)
      ? Math.max(0, Math.min(parsed, line.available_quantity, line.requested_quantity))
      : 0;
    setQuantities((prev) => ({ ...prev, [line.item_id]: bounded }));
  };

  return (
    <div className="fixed inset-0 z-[70] bg-slate-950/50 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="fulfillment-title">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-dashboard-card border border-dashboard-border shadow-2xl overflow-hidden">
        <div className="p-5 border-b border-dashboard-border flex items-start justify-between gap-4">
          <div className="flex gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 id="fulfillment-title" className="font-bold text-slate-900 dark:text-slate-100">Insufficient stock</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Order {orderNumber}: {preview.requested_quantity} requested · {preview.suggested_quantity} currently available to confirm.
              </p>
            </div>
          </div>
          <button onClick={onClose} disabled={submitting} className="p-1.5 rounded-full text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {mode === "choice" ? (
            <>
              <div className="rounded-xl border border-amber-200 dark:border-amber-500/20 bg-amber-50/60 dark:bg-amber-500/5 p-4 text-sm text-slate-700 dark:text-slate-300">
                The original customer demand will remain recorded. Any unfulfilled quantity will be captured in Demand Gap.
              </div>

              <button
                disabled={submitting}
                onClick={onConfirmAvailable}
                className="w-full text-left p-4 rounded-xl border border-emerald-200 dark:border-emerald-500/20 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors"
              >
                <div className="font-bold text-emerald-700 dark:text-emerald-400">Confirm {preview.suggested_quantity} available units</div>
                <div className="text-xs text-slate-500 mt-1">Shortfall: {preview.requested_quantity - preview.suggested_quantity} units</div>
              </button>

              <button
                disabled={submitting}
                onClick={() => setMode("custom")}
                className="w-full text-left p-4 rounded-xl border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
              >
                <div className="font-bold text-slate-800 dark:text-slate-100">Change confirmed quantity</div>
                <div className="text-xs text-slate-500 mt-1">Use this when the customer accepts less than the available stock.</div>
              </button>

              <button
                disabled={submitting}
                onClick={onCancelFull}
                className="w-full text-left p-4 rounded-xl border border-rose-200 dark:border-rose-500/20 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
              >
                <div className="font-bold text-rose-700 dark:text-rose-400">Cancel entire order</div>
                <div className="text-xs text-slate-500 mt-1">No inventory will be deducted. Full original demand will be recorded as lost.</div>
              </button>
            </>
          ) : (
            <>
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {preview.lines.map((line) => (
                  <div key={line.item_id} className="rounded-xl border border-dashboard-border p-3 flex items-center justify-between gap-4">
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      <div className="font-semibold text-slate-700 dark:text-slate-300">Requested {line.requested_quantity}</div>
                      <div>Available {line.available_quantity}</div>
                    </div>
                    <input
                      type="number"
                      min={0}
                      max={Math.min(line.requested_quantity, line.available_quantity)}
                      value={quantities[line.item_id] ?? 0}
                      onChange={(e) => updateQty(line, e.target.value)}
                      className="w-24 px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-dashboard-inset text-sm font-bold text-right"
                    />
                  </div>
                ))}
              </div>

              <div className="rounded-xl bg-slate-50 dark:bg-dashboard-inset p-3 flex justify-between text-sm">
                <span className="text-slate-500">Will confirm</span>
                <span className="font-bold text-slate-800 dark:text-slate-100">{confirmedTotal} of {preview.requested_quantity}</span>
              </div>

              <div className="flex justify-end gap-2">
                <button disabled={submitting} onClick={() => setMode("choice")} className="px-4 py-2 text-sm font-bold text-slate-500 hover:bg-slate-50 dark:hover:bg-white/5 rounded-lg">Back</button>
                <button
                  disabled={submitting || confirmedTotal <= 0}
                  onClick={() => onConfirmCustom(quantities)}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-sm font-bold rounded-lg flex items-center gap-2"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  Confirm {confirmedTotal}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
