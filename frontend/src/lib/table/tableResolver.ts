import {
  ColumnId,
  TableDefinition,
  TableViewPreference,
  ResolvedTableColumns,
  TableColumnDefinition,
} from "@/types/table";

/**
 * Reconciles a TableDefinition with durable user preferences.
 * 
 * Guarantees:
 * 1. Default mode cleanly adapts when Product changes default columns in future versions.
 * 2. Custom mode preserves the user's personal selection and order.
 * 3. Required columns are ALWAYS visible and cannot be hidden.
 * 4. Unsupported or deprecated columns are safely filtered out.
 * 5. Newly added supported columns are discoverable in the Manage Columns UI.
 */
export function resolveEffectiveColumns<TRow>(
  tableDef: TableDefinition<TRow>,
  preference?: TableViewPreference | null
): ResolvedTableColumns<TRow> {
  const supportedColumns = tableDef.columns.filter((c) => c.supported);
  const supportedMap = new Map<ColumnId, TableColumnDefinition<TRow>>(
    supportedColumns.map((c) => [c.id, c])
  );
  const requiredSet = new Set<ColumnId>(tableDef.requiredColumns || []);

  const isCustom = preference?.preference_mode === "custom";

  let orderedColumnIds: ColumnId[] = [];
  let visibleColumnIdList: ColumnId[] = [];

  if (isCustom && preference) {
    // 1. Start from user's custom column order, keeping only currently supported columns
    const seenIds = new Set<ColumnId>();
    for (const colId of preference.column_order || []) {
      if (supportedMap.has(colId) && !seenIds.has(colId)) {
        orderedColumnIds.push(colId);
        seenIds.add(colId);
      }
    }

    // 2. Append any supported columns that weren't in user's saved order (e.g. newly introduced columns)
    for (const col of supportedColumns) {
      if (!seenIds.has(col.id)) {
        orderedColumnIds.push(col.id);
        seenIds.add(col.id);
      }
    }

    // 3. User's visible columns
    const userVisibleSet = new Set<ColumnId>(preference.visible_columns || []);
    // Always include required columns
    const reqCols = tableDef.requiredColumns || [];
    for (let i = 0; i < reqCols.length; i++) {
      userVisibleSet.add(reqCols[i]);
    }

    // Visible columns in the determined order
    for (const colId of orderedColumnIds) {
      if (userVisibleSet.has(colId) && supportedMap.has(colId)) {
        visibleColumnIdList.push(colId);
      }
    }
  } else {
    // Default Mode: Follow product defaultColumnOrder
    const seenIds = new Set<ColumnId>();
    for (const colId of tableDef.defaultColumnOrder || []) {
      if (supportedMap.has(colId) && !seenIds.has(colId)) {
        orderedColumnIds.push(colId);
        seenIds.add(colId);
      }
    }

    // Append any remaining supported columns
    for (const col of supportedColumns) {
      if (!seenIds.has(col.id)) {
        orderedColumnIds.push(col.id);
        seenIds.add(col.id);
      }
    }

    // Visible columns for default mode
    for (const colId of orderedColumnIds) {
      const col = supportedMap.get(colId);
      if (col && (col.defaultVisible || requiredSet.has(colId))) {
        visibleColumnIdList.push(colId);
      }
    }
  }

  // Ensure any required columns are in visible list
  const reqCols = tableDef.requiredColumns || [];
  for (let i = 0; i < reqCols.length; i++) {
    const reqId = reqCols[i];
    if (!visibleColumnIdList.includes(reqId) && supportedMap.has(reqId)) {
      visibleColumnIdList.unshift(reqId);
    }
  }

  const orderedColumns = orderedColumnIds
    .map((id) => supportedMap.get(id)!)
    .filter(Boolean);

  const visibleColumnIds = new Set<ColumnId>(visibleColumnIdList);
  const visibleColumns = orderedColumns.filter((col) => visibleColumnIds.has(col.id));

  return {
    allColumns: supportedColumns,
    orderedColumns,
    visibleColumns,
    visibleColumnIds,
    isCustom,
  };
}
