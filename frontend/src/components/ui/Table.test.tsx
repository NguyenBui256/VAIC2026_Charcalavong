/* Test: Table — sticky headers, row hover, selected row, bulk bar (UX-DR6).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Table, { type TableColumn } from "./Table";

interface TestRow {
  id: string;
  name: string;
  status: string;
}

const rows: TestRow[] = [
  { id: "r1", name: "Alpha", status: "running" },
  { id: "r2", name: "Beta", status: "success" },
  { id: "r3", name: "Gamma", status: "error" },
];

const columns: TableColumn<TestRow>[] = [
  { key: "name", header: "Name" },
  { key: "status", header: "Status" },
];

describe("Table", () => {
  it("renders headers and rows", () => {
    render(<Table columns={columns} rows={rows} rowId={(r) => r.id} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
  });

  it("renders custom cell via render prop", () => {
    const cols: TableColumn<TestRow>[] = [
      { key: "name", header: "Name", render: (r) => <strong>{r.name}</strong> },
    ];
    render(<Table columns={cols} rows={rows} rowId={(r) => r.id} />);
    expect(screen.getByText("Alpha").tagName).toBe("STRONG");
  });

  it("fires onRowClick when a row is clicked", () => {
    const onRowClick = vi.fn();
    render(
      <Table columns={columns} rows={rows} rowId={(r) => r.id} onRowClick={onRowClick} />,
    );
    fireEvent.click(screen.getByTestId("vaic-table-row-r2"));
    expect(onRowClick).toHaveBeenCalledWith(rows[1], 1);
  });

  it("marks selected rows with vaic-table-row-selected class", () => {
    const selected = new Set<string>(["r2"]);
    render(
      <Table
        columns={columns}
        rows={rows}
        rowId={(r) => r.id}
        selectedRowIds={selected}
      />,
    );
    const r2 = screen.getByTestId("vaic-table-row-r2");
    expect(r2.className).toContain("vaic-table-row-selected");
    expect(r2).toHaveAttribute("data-selected", "true");
  });

  it("renders checkbox column when selectable=true", () => {
    render(
      <Table
        columns={columns}
        rows={rows}
        rowId={(r) => r.id}
        selectable
        selectedIds={new Set<string>()}
      />,
    );
    expect(screen.getByTestId("vaic-table-select-all")).toBeInTheDocument();
    rows.forEach((r) => {
      expect(screen.getByTestId(`vaic-table-select-${r.id}`)).toBeInTheDocument();
    });
  });

  it("renders bulk action bar when rows are selected", () => {
    render(
      <Table
        columns={columns}
        rows={rows}
        rowId={(r) => r.id}
        selectable
        selectedIds={new Set<string>(["r1", "r2"])}
        bulkActionBar={<button>Bulk Delete</button>}
      />,
    );
    expect(screen.getByTestId("vaic-table-bulk-bar")).toBeInTheDocument();
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bulk Delete" })).toBeInTheDocument();
  });

  it("does not render bulk bar when no rows selected", () => {
    render(
      <Table
        columns={columns}
        rows={rows}
        rowId={(r) => r.id}
        selectable
        selectedIds={new Set<string>()}
        bulkActionBar={<button>Bulk Delete</button>}
      />,
    );
    expect(screen.queryByTestId("vaic-table-bulk-bar")).not.toBeInTheDocument();
  });

  it("renders empty state when rows is empty", () => {
    render(
      <Table
        columns={columns}
        rows={[]}
        rowId={(r) => r.id}
        emptyState={<div>No data</div>}
      />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("toggles individual row selection via onToggleRow", () => {
    const onToggleRow = vi.fn();
    render(
      <Table
        columns={columns}
        rows={rows}
        rowId={(r) => r.id}
        selectable
        selectedIds={new Set<string>()}
        onToggleRow={onToggleRow}
      />,
    );
    fireEvent.click(screen.getByTestId("vaic-table-select-r2"));
    expect(onToggleRow).toHaveBeenCalledWith("r2");
  });
});
