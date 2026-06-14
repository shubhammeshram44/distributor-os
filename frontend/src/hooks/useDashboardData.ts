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
}

export interface OrderDetail {
  sku_id: string;
  brand: string;
  category: string;
  pack_size: string;
  quantity: number;
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

export function useDashboardData(activeTenantId: string) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentOrders, setRecentOrders] = useState<RecentOrder[]>([]);
  const [donutData, setDonutData] = useState<DonutSegment[]>([]);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [selectedOrderDetails, setSelectedOrderDetails] = useState<OrderDetail[] | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStaticData = useCallback(async () => {
    try {
      // Fetch Metrics
      const metricsResp = await fetch(`${BASE_URL}/api/v1/dashboard/metrics?tenant_id=${activeTenantId}`);
      if (!metricsResp.ok) throw new Error("Failed to fetch dashboard metrics");
      const metricsData = await metricsResp.json();
      setMetrics(metricsData);

      // Fetch Recent Orders
      const ordersResp = await fetch(`${BASE_URL}/api/v1/dashboard/recent-orders?tenant_id=${activeTenantId}`);
      if (!ordersResp.ok) throw new Error("Failed to fetch recent orders");
      const ordersData = await ordersResp.json();
      setRecentOrders(ordersData);

      // Fetch Donut Data
      const donutResp = await fetch(`${BASE_URL}/api/v1/dashboard/collections-donut?tenant_id=${activeTenantId}`);
      if (!donutResp.ok) throw new Error("Failed to fetch collections donut");
      const donutResData = await donutResp.json();
      setDonutData(donutResData);
      
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load dashboard data");
    }
  }, [activeTenantId]);

  const fetchPolledData = useCallback(async () => {
    try {
      // Fetch Activity Feed (Polled)
      const activityResp = await fetch(`${BASE_URL}/api/v1/dashboard/recent-activity?tenant_id=${activeTenantId}`);
      if (activityResp.ok) {
        const activityData = await activityResp.json();
        setActivities(activityData);
      }
    } catch (err) {
      console.error("Activity feed poll failed:", err);
    }
  }, [activeTenantId]);

  const fetchOrderDetails = async (orderId: string) => {
    setLoadingDetails(true);
    try {
      const resp = await fetch(`${BASE_URL}/api/v1/dashboard/order-details/${orderId}`);
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

  // Initial and Tenant-switch load
  useEffect(() => {
    if (activeTenantId) {
      fetchStaticData();
      fetchPolledData();
    }
  }, [activeTenantId, fetchStaticData, fetchPolledData]);

  // Activity feed polling setup (every 5 seconds)
  useEffect(() => {
    if (!activeTenantId) return;

    const interval = setInterval(() => {
      fetchPolledData();
    }, 5000);

    return () => clearInterval(interval);
  }, [activeTenantId, fetchPolledData]);

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
    error
  };
}
