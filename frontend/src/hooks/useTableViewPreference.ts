"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  ColumnId,
  TableDefinition,
  TableViewPreference,
  ResolvedTableColumns,
} from "@/types/table";
import { resolveEffectiveColumns } from "@/lib/table/tableResolver";

const CACHE_PREFIX = "distroos_tbl_pref";

export function useTableViewPreference<TRow>(
  pageKey: string,
  tableDef: TableDefinition<TRow>,
  tenantId?: string
) {
  const [preference, setPreference] = useState<TableViewPreference | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const cacheKey = `${CACHE_PREFIX}_${tenantId || "default"}_${pageKey}`;

  // 1. Initial hydrate from localStorage cache for instant render without layout shift
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const cached = localStorage.getItem(cacheKey);
      if (cached) {
        const parsed = JSON.parse(cached) as TableViewPreference;
        if (parsed && parsed.page_key === pageKey) {
          setPreference(parsed);
          setIsLoading(false);
        }
      }
    } catch (e) {
      console.warn("Failed to read cached table preference:", e);
    }
  }, [cacheKey, pageKey]);

  // 2. Fetch server-side durable preference
  const fetchServerPreference = useCallback(async () => {
    if (!tenantId) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(
        `${apiBase}/api/v1/table-preferences/${pageKey}?tenant_id=${tenantId}`,
        {
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      if (resp.ok) {
        const data: TableViewPreference = await resp.json();
        setPreference(data);
        if (typeof window !== "undefined") {
          localStorage.setItem(cacheKey, JSON.stringify(data));
        }
      }
    } catch (err) {
      console.error("Failed to load table preference from server:", err);
    } finally {
      setIsLoading(false);
    }
  }, [pageKey, tenantId, cacheKey]);

  useEffect(() => {
    fetchServerPreference();
  }, [fetchServerPreference]);

  // Sync to server with debounce
  const syncPreferenceToServer = useCallback(
    (newPref: TableViewPreference) => {
      if (!tenantId) return;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(async () => {
        setIsSaving(true);
        try {
          const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
          const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
          await fetch(`${apiBase}/api/v1/table-preferences/${pageKey}?tenant_id=${tenantId}`, {
            method: "PUT",
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              preference_mode: newPref.preference_mode,
              visible_columns: newPref.visible_columns,
              column_order: newPref.column_order,
              version: newPref.version,
            }),
          });
        } catch (err) {
          console.error("Failed to save table preference to server:", err);
        } finally {
          setIsSaving(false);
        }
      }, 400);
    },
    [pageKey, tenantId]
  );

  // Compute resolved columns
  const resolved = useMemo<ResolvedTableColumns<TRow>>(() => {
    return resolveEffectiveColumns(tableDef, preference);
  }, [tableDef, preference]);

  // Actions
  const toggleColumn = useCallback(
    (colId: ColumnId) => {
      // Cannot toggle required columns
      if (tableDef.requiredColumns?.includes(colId)) return;

      const currentVisibleIds = Array.from(resolved.visibleColumnIds);
      const currentOrder = resolved.orderedColumns.map((c) => c.id);

      const nextVisible = currentVisibleIds.includes(colId)
        ? currentVisibleIds.filter((id) => id !== colId)
        : [...currentVisibleIds, colId];

      const newPref: TableViewPreference = {
        page_key: pageKey,
        preference_mode: "custom",
        visible_columns: nextVisible,
        column_order: currentOrder,
        version: tableDef.version,
        updated_at: new Date().toISOString(),
      };

      setPreference(newPref);
      if (typeof window !== "undefined") {
        localStorage.setItem(cacheKey, JSON.stringify(newPref));
      }
      syncPreferenceToServer(newPref);
    },
    [tableDef, resolved, pageKey, cacheKey, syncPreferenceToServer]
  );

  const reorderColumns = useCallback(
    (newOrder: ColumnId[]) => {
      const currentVisibleIds = Array.from(resolved.visibleColumnIds);
      const newPref: TableViewPreference = {
        page_key: pageKey,
        preference_mode: "custom",
        visible_columns: currentVisibleIds,
        column_order: newOrder,
        version: tableDef.version,
        updated_at: new Date().toISOString(),
      };

      setPreference(newPref);
      if (typeof window !== "undefined") {
        localStorage.setItem(cacheKey, JSON.stringify(newPref));
      }
      syncPreferenceToServer(newPref);
    },
    [tableDef, resolved, pageKey, cacheKey, syncPreferenceToServer]
  );

  const moveColumn = useCallback(
    (colId: ColumnId, direction: "up" | "down") => {
      const currentOrder = [...resolved.orderedColumns.map((c) => c.id)];
      const index = currentOrder.indexOf(colId);
      if (index === -1) return;

      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= currentOrder.length) return;

      // Swap
      const temp = currentOrder[index];
      currentOrder[index] = currentOrder[targetIndex];
      currentOrder[targetIndex] = temp;

      reorderColumns(currentOrder);
    },
    [resolved, reorderColumns]
  );

  const resetToDefault = useCallback(async () => {
    const defaultVisible = tableDef.defaultColumnOrder.filter((id) => {
      const col = tableDef.columns.find((c) => c.id === id);
      return col?.defaultVisible || tableDef.requiredColumns?.includes(id);
    });

    const newPref: TableViewPreference = {
      page_key: pageKey,
      preference_mode: "default",
      visible_columns: defaultVisible,
      column_order: [...tableDef.defaultColumnOrder],
      version: tableDef.version,
      updated_at: new Date().toISOString(),
    };

    setPreference(newPref);
    if (typeof window !== "undefined") {
      localStorage.setItem(cacheKey, JSON.stringify(newPref));
    }

    if (tenantId) {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
        await fetch(`${apiBase}/api/v1/table-preferences/${pageKey}?tenant_id=${tenantId}`, {
          method: "DELETE",
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch (err) {
        console.error("Failed to delete table preference on server:", err);
      }
    }
  }, [tableDef, pageKey, cacheKey, tenantId]);

  return {
    ...resolved,
    preference,
    isLoading,
    isSaving,
    toggleColumn,
    reorderColumns,
    moveColumn,
    resetToDefault,
  };
}
