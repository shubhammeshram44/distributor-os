"use client";

import React, { useEffect, useRef, useState } from "react";
import FulfillmentDecisionModal, { FulfillmentPreview } from "@/components/FulfillmentDecisionModal";

type PendingConfirmation = {
  orderId: string;
  orderNumber: string;
  originalInput: RequestInfo | URL;
  originalInit?: RequestInit;
  originalBody: any;
  resolve: (value: Response) => void;
  reject: (reason?: any) => void;
};

function jsonResponse(payload: any, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default function FulfillmentConfirmationInterceptor() {
  const nativeFetch = useRef<typeof window.fetch | null>(null);
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const [preview, setPreview] = useState<FulfillmentPreview | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    nativeFetch.current = window.fetch.bind(window);
    const originalFetch = nativeFetch.current;

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const match = url.match(/\/api\/v1\/orders\/([^/]+)\/batch-confirm(?:\?|$)/);
      if (!match || (init?.method || "GET").toUpperCase() !== "POST") {
        return originalFetch(input, init);
      }

      let body: any = {};
      try {
        body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
      } catch {
        return originalFetch(input, init);
      }

      const orderId = match[1];
      const apiBase = url.split("/api/v1/orders/")[0];
      try {
        const previewResp = await originalFetch(`${apiBase}/api/v1/orders/${orderId}/fulfillment-preview`, {
          method: "POST",
          credentials: init?.credentials || "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ resolved_items: body.resolved_items || [] }),
        });
        if (!previewResp.ok) return originalFetch(input, init);
        const stockPreview: FulfillmentPreview = await previewResp.json();
        if (!stockPreview.has_shortage) return originalFetch(input, init);

        return await new Promise<Response>((resolve, reject) => {
          setPreview(stockPreview);
          setPending({
            orderId,
            orderNumber: orderId.slice(0, 8),
            originalInput: input,
            originalInit: init,
            originalBody: body,
            resolve,
            reject,
          });
        });
      } catch {
        return originalFetch(input, init);
      }
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  const finish = (response: Response) => {
    pending?.resolve(response);
    setPending(null);
    setPreview(null);
  };

  const dismiss = () => {
    finish(jsonResponse({ detail: "Confirmation cancelled by user." }, 409));
  };

  const decide = async (action: "CONFIRM_AVAILABLE" | "CONFIRM_CUSTOM" | "CANCEL_FULL", quantities?: Record<string, number>) => {
    if (!pending || !nativeFetch.current) return;
    setSubmitting(true);
    try {
      const originalUrl = typeof pending.originalInput === "string"
        ? pending.originalInput
        : pending.originalInput instanceof URL
          ? pending.originalInput.toString()
          : pending.originalInput.url;
      const apiBase = originalUrl.split("/api/v1/orders/")[0];
      const line_decisions = quantities
        ? Object.entries(quantities).map(([item_id, approved_quantity]) => ({ item_id, approved_quantity }))
        : [];
      const resp = await nativeFetch.current(`${apiBase}/api/v1/orders/${pending.orderId}/fulfillment-decision`, {
        method: "POST",
        credentials: pending.originalInit?.credentials || "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          line_decisions,
          resolved_items: pending.originalBody.resolved_items || [],
          invoice_type: pending.originalBody.invoice_type || null,
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        finish(jsonResponse({ detail: data.detail || "Fulfillment decision failed." }, resp.status));
        return;
      }
      finish(jsonResponse({
        ...data,
        message: action === "CANCEL_FULL" ? "Order cancelled due to stock shortage." : "Order confirmed successfully.",
      }));
    } catch (error: any) {
      finish(jsonResponse({ detail: error?.message || "Fulfillment decision failed." }, 500));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <FulfillmentDecisionModal
      open={Boolean(pending && preview)}
      orderNumber={pending?.orderNumber || ""}
      preview={preview}
      submitting={submitting}
      onClose={dismiss}
      onConfirmAvailable={() => decide("CONFIRM_AVAILABLE")}
      onConfirmCustom={(quantities) => decide("CONFIRM_CUSTOM", quantities)}
      onCancelFull={() => decide("CANCEL_FULL")}
    />
  );
}
