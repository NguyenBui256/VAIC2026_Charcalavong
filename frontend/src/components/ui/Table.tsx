/* Story 1.9 — Table primitive (UX-DR6).
 *
 * Features: sticky headers, row hover (bg-surface-muted), selected row
 * (bg-primary-soft + left border), optional bulk action bar.
 *
 * The component is headless-friendly: callers pass column defs + rows.
 */

import type { ReactNode } from "react";

export interface TableColumn<T> {
  /** Unique key — maps to the row object property or used for custom render. */
  key: string;
  /** Header label. */
  header: ReactNode;
  /** Custom cell renderer. */
  render?: (row: T, index: number) => ReactNode;
  /** Optional width (CSS value). */
  width?: string;
  /** Text alignment for header + cells. Defaults to "left". */
  align?: "left" | "center" | "right";
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  rows: T[];
  /** Returns the unique row id (for key prop). */
  rowId: (row: T, index: number) => string;
  /** Indices or row ids of selected rows. */
  selectedRowIds?: Set<string>;
  /** Click handler for a row. */
  onRowClick?: (row: T, index: number) => void;
  /** Optional checkbox column for bulk selection. */
  selectable?: boolean;
  /** Set of selected row ids for checkboxes. */
  selectedIds?: Set<string>;
  /** Toggle selection callback. */
  onToggleRow?: (rowId: string) => void;
  /** Toggle-all callback. */
  onToggleAll?: () => void;
  /** Whether all currently filtered rows are selected. */
  allSelected?: boolean;
  /** Bulk action bar content (rendered when rows are selected). */
  bulkActionBar?: ReactNode;
  /** Optional caption for screen readers (not visually shown). */
  caption?: string;
  /** Sticky header offset (e.g. if table is inside a scrolled container). Defaults to 0. */
  stickyHeaderOffset?: number;
  /** Empty state node rendered when rows is empty. */
  emptyState?: ReactNode;
}

export default function Table<T>({
  columns,
  rows,
  rowId,
  selectedRowIds,
  onRowClick,
  selectable = false,
  selectedIds,
  onToggleRow,
  onToggleAll,
  allSelected = false,
  bulkActionBar,
  caption,
  stickyHeaderOffset = 0,
  emptyState,
}: TableProps<T>) {
  const hasBulkBar = Boolean(bulkActionBar && selectedIds && selectedIds.size > 0);

  return (
    <div className="vaic-table-wrapper" data-testid="vaic-table">
      <table className="vaic-table">
        {caption && (
          /* Visually hidden but readable by screen readers. Uses the clip
           * technique instead of left:-9999px, which pushes content off-canvas
           * and inflates scrollWidth (phantom horizontal scrollbar). */
          <caption
            style={{
              position: "absolute",
              width: "1px",
              height: "1px",
              padding: 0,
              margin: "-1px",
              overflow: "hidden",
              clip: "rect(0, 0, 0, 0)",
              whiteSpace: "nowrap",
              border: 0,
            }}
          >
            {caption}
          </caption>
        )}
        <thead>
          <tr>
            {selectable && (
              <th style={{ width: "40px", padding: "var(--space-2)" }}>
                <input
                  type="checkbox"
                  aria-label="Select all rows"
                  checked={allSelected}
                  onChange={onToggleAll ?? undefined}
                  style={{ cursor: "pointer" }}
                  data-testid="vaic-table-select-all"
                />
              </th>
            )}
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  width: col.width,
                  textAlign: col.align,
                  top: stickyHeaderOffset > 0 ? `${stickyHeaderOffset}px` : undefined,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && emptyState ? (
            <tr>
              <td
                colSpan={columns.length + (selectable ? 1 : 0)}
                style={{ textAlign: "center", padding: "var(--space-12)" }}
              >
                {emptyState}
              </td>
            </tr>
          ) : (
            rows.map((row, index) => {
              const id = rowId(row, index);
              const isSelected = selectedRowIds?.has(id) ?? false;
              return (
                <tr
                  key={id}
                  className={isSelected ? "vaic-table-row-selected" : ""}
                  onClick={onRowClick ? () => onRowClick(row, index) : undefined}
                  style={onRowClick ? { cursor: "pointer" } : undefined}
                  data-testid={`vaic-table-row-${id}`}
                  data-selected={isSelected || undefined}
                >
                  {selectable && (
                    <td style={{ width: "40px", padding: "var(--space-2)" }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Select row ${index + 1}`}
                        checked={selectedIds?.has(id) ?? false}
                        onChange={onToggleRow ? () => onToggleRow(id) : undefined}
                        style={{ cursor: "pointer" }}
                        data-testid={`vaic-table-select-${id}`}
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td key={col.key} style={col.align ? { textAlign: col.align } : undefined}>
                      {col.render ? col.render(row, index) : (row as Record<string, ReactNode>)[col.key]}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      {hasBulkBar && (
        <div className="vaic-table-bulk-bar" data-testid="vaic-table-bulk-bar">
          {selectedIds && (
            <span style={{ fontWeight: 600 }}>
              {selectedIds.size} selected
            </span>
          )}
          {bulkActionBar}
        </div>
      )}
    </div>
  );
}
