"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import CollectionsDonut from "@/components/CollectionsDonut";
// LiveDeliveries import removed 2026-06-28 — replaced by DemandGapCard in the bottom grid.
// The component file (LiveDeliveries.tsx) is preserved on disk for future use.
import InventorySummary from "@/components/InventorySummary";
import DemandGapCard from "@/components/DemandGapCard";
import CashFlowForecastCard from "@/components/CashFlowForecastCard";
import TopProductsCard from "@/components/TopProductsCard";
// ActivityFeed replaced with simple link (see bottom of dashboard layout)
import OnboardingChecklist from "@/components/OnboardingChecklist";
import { useDashboardData, DashboardMetrics } from "@/hooks/useDashboardData";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { Skeleton, SkeletonCard, SkeletonChartCard } from "@/components/ui/Skeleton";
import { formatDateTime } from "@/utils/datetime";
import PlaceOrderModal from "@/components/PlaceOrderModal";
import RevenueTrendChart from "@/components/RevenueTrendChart";
import { BarChart3, PackagePlus, Plus, ReceiptText, RefreshCw, UserPlus } from "lucide-react";
import MetricInfo from "@/components/ui/MetricInfo";


export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [tenantId, setTenantId] = useState("");
  const [userProfile, setUserProfile] = useState<any>(null);
  const [isHydrating, setIsHydrating] = useState(true);
  // ... remainder continues in file - USE FULL CONTENT
}
