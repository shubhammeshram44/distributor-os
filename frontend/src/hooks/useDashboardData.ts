import { useState, useEffect, useCallback } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface DashboardMetrics {
  total_sales: number;
  total_sales_change: number;
  orders_count: number;
  orders_count_change: number;
  average_order_value: number;
  average_order_value_change: number;
  outstanding_collections: number;
  outstanding_collections_change: number;
  low_stock_count?: number;
  out_of_stock_count?: number;
  total_skus_count?: number;
  inventory_value?: string;
  overdue_60_count?: number;
  total_skus?: number;
  total_inventory_value?: number;
}

export interface RecentOrder {
  id: string;
  order_id: string;
  customer: string;
  channel: string;
  amount: number;
  status: string;
  created_on?: string;
  eta: string;
  line_items?: OrderDetail[];
}

export interface OrderDetail {
  id: string;
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
  allocated_quantity?: number | null;
  unit_price: number;
  total_price: number;
}

export interface DonutSegment {
  name: string;
  value: number;
  percentage: number;
}

export interface ActivityEvent {
  message: string;
  time: string;
  category: string;
}

export function useDashboardData(
  activeTenantId: string,
  startDate?: string,
  endDate?: string,
  isAuthenticated: boolean = true,
  firebaseAuthExpiredFlag: boolean = false
) {

  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentOrders, setRecentOrders] = useState<RecentOrder[]>([]);
  const [donutData, setDonutData] = useState<DonutSegment[]>([]);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [selectedOrderDetails, setSelectedOrderDetails] = useState<OrderDetail[] | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchStaticData = useCallback(async () => {
    if (!activeTenantId || !isAuthenticated || firebaseAuthExpiredFlag) return;
    setIsLoading(true);
    try {
      const options = {
        method: "GET",
        credentials: "include" as const,
        headers: {
          "Content-Type": "application/json",
        }
      };

      // Fetch consolidated overview with optional date filters
      let overviewUrl = `${BASE_URL}/api/v1/dashboard/overview?tenant_id=${activeTenantId}`;
      if (startDate) {
        overviewUrl += `&start_date=${encodeURIComponent(startDate)}`;
      }
      if (endDate) {
        overviewUrl += `&end_date=${encodeURIComponent(endDate)}`;
      }
      const overviewResp = await fetch(overviewUrl, options);
      if (!overviewResp.ok) throw new Error("Failed to fetch dashboard overview");
      const overviewData = await overviewResp.json();

      setMetrics(overviewData.metrics);
      setRecentOrders(overviewData.recent_orders);
      setDonutData(overviewData.donut_data);
      
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setIsLoading(false);
    }
  }, [activeTenantId, startDate, endDate]);

  const fetchPolledData = useCallback(async () => {
    if (!activeTenantId || !isAuthenticated || firebaseAuthExpiredFlag) return;
    try {
      const options = {
        method: "GET",
        credentials: "include" as const,
        headers: {
          "Content-Type": "application/json",
        }
      };

      // Fetch Activity Feed (Polled)
      const activityResp = await fetch(`${BASE_URL}/api/v1/dashboard/recent-activity?tenant_id=${activeTenantId}`, options);
      if (activityResp.ok) {
        const activityData = await activityResp.json();
        setActivities(activityData);
      }
    } catch (err) {
      console.error("Activity feed poll failed:", err);
    }
  }, [activeTenantId]);

  const fetchOrderDetails = async (orderId: string) => {
    if (!isAuthenticated || firebaseAuthExpiredFlag) return;
    setLoadingDetails(true);
    try {
      const options = {
        method: "GET",
        credentials: "include" as const,
        headers: {
          "Content-Type": "application/json",
        }
      };
      const resp = await fetch(`${BASE_URL}/api/v1/dashboard/order-details/${orderId}`, options);
      if (!resp.ok) throw new Error("Failed to load order line item details");
      const data = await resp.json();
      setSelectedOrderDetails(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const closeDetails = () => {
    setSelectedOrderDetails(null);
  };

  // Intercept expired or missing auth states before executing queries
  useEffect(() => {
    if (!isAuthenticated || firebaseAuthExpiredFlag) {
      localStorage.removeItem("tenantId");
      localStorage.removeItem("tenant_id");
      window.location.href = "/login";
    }
  }, [isAuthenticated, firebaseAuthExpiredFlag]);

  // Initial and Tenant-switch or Date-switch load
  useEffect(() => {
    if (activeTenantId && isAuthenticated && !firebaseAuthExpiredFlag) {
      fetchStaticData();
      fetchPolledData();
    }
  }, [activeTenantId, startDate, endDate, isAuthenticated, firebaseAuthExpiredFlag, fetchStaticData, fetchPolledData]);

  // Activity feed polling setup (every 5 seconds)
  useEffect(() => {
    if (!activeTenantId || !isAuthenticated || firebaseAuthExpiredFlag) return;

    const interval = setInterval(() => {
      fetchPolledData();
    }, 5000);

    return () => clearInterval(interval);
  }, [activeTenantId, isAuthenticated, firebaseAuthExpiredFlag, fetchPolledData]);


  return {
    metrics,
    recentOrders,
    donutData,
    activities,
    selectedOrderDetails,
    loadingDetails,
    fetchOrderDetails,
    closeDetails,
    refreshAll: fetchStaticData,
    error,
    isLoading
  };
}
