/**
 * Unconditionally quotes every cell to prevent CSV injection.
 * Cells starting with =, +, -, @, \t, or \r could be interpreted
 * as formulas by spreadsheet programs — quoting neutralises this.
 */
export function exportToCsv<T>(
  filename: string,
  data: T[],
  columns: Array<{ key: keyof T & string; header: string }>,
): void {
  const csv = generateCsv(data, columns);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function generateCsv<T>(
  data: T[],
  columns: Array<{ key: keyof T & string; header: string }>,
): string {
  const quoteCell = (value: unknown): string => {
    const str = value == null ? "" : String(value);
    return `"${str.replace(/"/g, '""')}"`;
  };

  const header = columns.map((c) => quoteCell(c.header)).join(",");
  const rows = data.map((row) => columns.map((c) => quoteCell(row[c.key])).join(","));
  return [header, ...rows].join("\n");
}
