"use client";

import React from "react";
import { InboxIcon, BarChart3, Package, Users, Truck, CreditCard } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  customIcon?: "orders" | "products" | "customers" | "inventory" | "shipments" | "collections" | "default";
}

const iconMap = {
  orders: ShoppingBag,
  products: Package,
  customers: Users,
  inventory: BarChart3,
  shipments: Truck,
  collections: CreditCard,
  default: InboxIcon
};

function ShoppingBag(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  customIcon = "default"
}: EmptyStateProps) {
  const IconComponent = customIcon !== "default" ? iconMap[customIcon as keyof typeof iconMap] : iconMap.default;

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mb-6">
        <div className="text-slate-400">
          {icon || <IconComponent className="w-10 h-10" />}
        </div>
      </div>
      
      <h3 className="text-lg font-bold text-slate-800 mb-2 text-center">{title}</h3>
      <p className="text-sm text-slate-500 text-center max-w-xs mb-6">{description}</p>
      
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-brand-blue text-white text-sm font-semibold rounded-lg hover:bg-brand-blueHover transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
