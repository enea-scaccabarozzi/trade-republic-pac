import { describe, expect, it, vi } from "vitest";
import { createRunsColumns } from "../runs-columns";

describe("createRunsColumns", () => {
  const onView = vi.fn();
  const onClone = vi.fn();
  const onDelete = vi.fn();

  it("returns the expected number of columns", () => {
    const columns = createRunsColumns({ onView, onClone, onDelete });
    expect(columns).toHaveLength(9);
  });

  it("has an actions column with noRowClick meta", () => {
    const columns = createRunsColumns({ onView, onClone, onDelete });
    const actionsCol = columns.find((c) => "id" in c && c.id === "actions");
    expect(actionsCol).toBeDefined();
    expect((actionsCol?.meta as { noRowClick?: boolean })?.noRowClick).toBe(true);
  });
});
