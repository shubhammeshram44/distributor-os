import { useState, useEffect, useCallback } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface TopMovingSku {
  sku_code: string;
  brand: string;
  category: string;
  pack_size?: string;
  total_quantity: number;
  total_revenue: number;
}

export interface SalesOverview {
  status: string;
  total_orders: number;
  status_distribution: Record<string, number>;
  top_moving_skus: TopMovingSku[];
}

/**
 * Thin wrapper around the existing `/api/v1/analytics/sales-overview` endpoint,
 * shared by the Top Products, Order Pipeline, and Alerts widgets on the
 * dashboard home page so we only issue one network request instead of three.
 */
export function useSalesOverview(activeTenantId: string) {
  const [data, setData] = useState<SalesOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverview = useCallback(async () => {
    if (!activeTenantId) return;
    setIsLoading(true);
    try {
      const token = localStorage.getItem("accessToken");
      const resp = await fetch(`${BASE_URL}/api/v1/analytics/sales-overview?tenant_id=${activeTenantId}`, {
        credentials: "include",
        headers: token ? { Authorization: "Bearer " + token } : {}
      });
      if (!resp.ok) throw new Error("Failed to fetch sales overview");
      setData(await resp.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sales overview");
    } finally {
      setIsLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  return { data, isLoading, error, refresh: fetchOverview };
}
