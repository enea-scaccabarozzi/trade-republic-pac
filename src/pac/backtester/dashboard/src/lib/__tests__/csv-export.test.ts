import { describe, expect, it, vi } from "vitest";
import { exportToCsv, generateCsv } from "../csv-export";

describe("generateCsv", () => {
  it("generates correct header and rows", () => {
    const data = [
      { name: "Alice", age: 30 },
      { name: "Bob", age: 25 },
    ];
    const columns = [
      { key: "name" as const, header: "Name" },
      { key: "age" as const, header: "Age" },
    ];
    const csv = generateCsv(data, columns);
    const lines = csv.split("\n");
    expect(lines[0]).toBe('"Name","Age"');
    expect(lines[1]).toBe('"Alice","30"');
    expect(lines[2]).toBe('"Bob","25"');
  });

  it("unconditionally quotes all cells", () => {
    const data = [{ value: "plain text" }];
    const columns = [{ key: "value" as const, header: "Value" }];
    const csv = generateCsv(data, columns);
    expect(csv).toContain('"plain text"');
  });

  it("safely quotes values starting with formula characters", () => {
    const dangerous = ["=SUM(A1)", "+cmd", "-calc", "@import", "\tcmd", "\rcmd"];
    for (const val of dangerous) {
      const data = [{ v: val }];
      const csv = generateCsv(data, [{ key: "v" as const, header: "V" }]);
      // Value should be wrapped in quotes
      expect(csv).toContain(`"${val}"`);
    }
  });

  it("escapes internal double-quotes", () => {
    const data = [{ v: 'He said "hello"' }];
    const csv = generateCsv(data, [{ key: "v" as const, header: "V" }]);
    expect(csv).toContain('"He said ""hello"""');
  });

  it("handles null and undefined values", () => {
    const data = [{ a: null, b: undefined }] as Array<Record<string, unknown>>;
    const columns = [
      { key: "a" as const, header: "A" },
      { key: "b" as const, header: "B" },
    ];
    const csv = generateCsv(data, columns);
    expect(csv).toContain('"","');
  });

  it("handles values with commas", () => {
    const data = [{ v: "foo, bar" }];
    const csv = generateCsv(data, [{ key: "v" as const, header: "V" }]);
    expect(csv).toContain('"foo, bar"');
  });
});

describe("exportToCsv", () => {
  it("triggers file download", () => {
    const mockClick = vi.fn();
    const mockCreateObjectURL = vi.fn(() => "blob:test");
    const mockRevokeObjectURL = vi.fn();
    const mockCreateElement = vi.spyOn(document, "createElement");

    globalThis.URL.createObjectURL = mockCreateObjectURL;
    globalThis.URL.revokeObjectURL = mockRevokeObjectURL;

    mockCreateElement.mockReturnValue({
      href: "",
      download: "",
      click: mockClick,
    } as unknown as HTMLAnchorElement);

    exportToCsv("test.csv", [{ a: 1 }], [{ key: "a" as const, header: "A" }]);

    expect(mockClick).toHaveBeenCalledOnce();
    expect(mockCreateObjectURL).toHaveBeenCalledOnce();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith("blob:test");

    mockCreateElement.mockRestore();
  });
});
