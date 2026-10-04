import React from "react";

export type ColumnId = string;

export interface TableColumnDefinition<TRow = any> {
  id: ColumnId;
  label: string;
  description?: string;
  source?: string;
  supported: boolean;
  defaultVisible: boolean;
  required?: boolean; // Pinned / cannot be hidden by user (e.g. primary identifier)
  sortable?: boolean;
  filterable?: boolean;
  align?: "left" | "center" | "right";
  minWidth?: string | number;
  width?: string | number;
  headerTooltip?: string;
  renderCell: (row: TRow, context?: any) => React.ReactNode;
  renderHeader?: () => React.ReactNode;
}

export interface TableDefinition<TRow = any> {
  pageKey: string;
  version: number;
  columns: TableColumnDefinition<TRow>[];
  defaultColumnOrder: ColumnId[];
  requiredColumns: ColumnId[];
}

export interface TableViewPreference {
  page_key: string;
  preference_mode: "default" | "custom";
  visible_columns: ColumnId[];
  column_order: ColumnId[];
  version: number;
  updated_at?: string | null;
}

export interface ResolvedTableColumns<TRow = any> {
  allColumns: TableColumnDefinition<TRow>[];
  orderedColumns: TableColumnDefinition<TRow>[];
  visibleColumns: TableColumnDefinition<TRow>[];
  visibleColumnIds: Set<ColumnId>;
  isCustom: boolean;
}
