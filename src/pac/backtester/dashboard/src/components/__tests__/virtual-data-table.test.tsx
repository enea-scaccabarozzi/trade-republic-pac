import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VirtualDataTable } from "../virtual-data-table";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count, estimateSize }: { count: number; estimateSize: () => number }) => {
    const size = estimateSize();
    return {
      getVirtualItems: () =>
        Array.from({ length: count }, (_, i) => ({
          index: i,
          key: i,
          start: i * size,
          end: (i + 1) * size,
          size,
          lane: 0,
        })),
      getTotalSize: () => count * size,
    };
  },
}));

interface TestRow {
  id: string;
  name: string;
  value: number;
}

const columns = [
  { accessorKey: "name" as const, header: "Name" },
  { accessorKey: "value" as const, header: "Value" },
];

const data: TestRow[] = [
  { id: "1", name: "Alpha", value: 10 },
  { id: "2", name: "Beta", value: 20 },
  { id: "3", name: "Gamma", value: 30 },
];

describe("VirtualDataTable", () => {
  it("renders header row with all visible columns", () => {
    render(<VirtualDataTable columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
  });

  it("renders data rows", () => {
    render(<VirtualDataTable columns={columns} data={data} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("hides column when columnVisibility excludes it", () => {
    render(<VirtualDataTable columns={columns} data={data} columnVisibility={{ value: false }} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.queryByText("Value")).not.toBeInTheDocument();
  });

  it("renders toolbar when provided", () => {
    render(
      <VirtualDataTable
        columns={columns}
        data={data}
        toolbar={() => <button type="button">Toolbar</button>}
      />,
    );
    expect(screen.getByText("Toolbar")).toBeInTheDocument();
  });

  it("renders empty state when data is empty", () => {
    render(<VirtualDataTable columns={columns} data={[]} emptyState={<span>Nothing here</span>} />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("applies getRowClassName to rendered rows", () => {
    const { container } = render(
      <VirtualDataTable
        columns={columns}
        data={data}
        getRowClassName={(row) => (row.value >= 20 ? "highlight-row" : "")}
      />,
    );
    const rows = container.querySelectorAll("tbody tr");
    // Alpha (10) → no class, Beta (20) → highlight, Gamma (30) → highlight
    expect(rows[0]?.className).not.toContain("highlight-row");
    expect(rows[1]?.className).toContain("highlight-row");
    expect(rows[2]?.className).toContain("highlight-row");
  });
});
