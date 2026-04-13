import { describe, expect, it } from "vitest";
import { jsonSchemaToZod } from "../schema-to-zod";

describe("jsonSchemaToZod", () => {
  it("returns empty schema for empty properties", () => {
    const result = jsonSchemaToZod({ properties: {} });
    expect(result.fields).toEqual([]);
    expect(result.defaults).toEqual({});
    expect(result.zodSchema.parse({})).toEqual({});
  });

  it("returns empty schema for missing properties key", () => {
    const result = jsonSchemaToZod({});
    expect(result.fields).toEqual([]);
  });

  it("converts string field to z.string()", () => {
    const result = jsonSchemaToZod({
      properties: { name: { type: "string" } },
      required: ["name"],
    });
    expect(result.fields).toHaveLength(1);
    expect(result.fields[0]?.type).toBe("string");
    expect(result.fields[0]?.required).toBe(true);
    expect(result.zodSchema.parse({ name: "hello" })).toEqual({ name: "hello" });
    expect(() => result.zodSchema.parse({ name: "" })).toThrow();
  });

  it("converts number field to z.number() with min/max", () => {
    const result = jsonSchemaToZod({
      properties: { age: { type: "number", minimum: 0, maximum: 120 } },
      required: ["age"],
    });
    expect(result.fields[0]?.type).toBe("number");
    expect(result.fields[0]?.minimum).toBe(0);
    expect(result.fields[0]?.maximum).toBe(120);
    expect(result.zodSchema.parse({ age: "30" })).toEqual({ age: 30 });
    expect(() => result.zodSchema.parse({ age: -1 })).toThrow();
    expect(() => result.zodSchema.parse({ age: 121 })).toThrow();
  });

  it("converts integer field to z.number().int()", () => {
    const result = jsonSchemaToZod({
      properties: { count: { type: "integer", minimum: 1, maximum: 10 } },
      required: ["count"],
    });
    expect(result.fields[0]?.type).toBe("integer");
    expect(result.zodSchema.parse({ count: "5" })).toEqual({ count: 5 });
    expect(() => result.zodSchema.parse({ count: 3.5 })).toThrow();
  });

  it("converts boolean field to z.boolean()", () => {
    const result = jsonSchemaToZod({
      properties: { enabled: { type: "boolean" } },
      required: ["enabled"],
    });
    expect(result.fields[0]?.type).toBe("boolean");
    expect(result.zodSchema.parse({ enabled: true })).toEqual({ enabled: true });
  });

  it("converts enum field to z.enum()", () => {
    const result = jsonSchemaToZod({
      properties: { color: { enum: ["red", "green", "blue"] } },
      required: ["color"],
    });
    expect(result.fields[0]?.type).toBe("enum");
    expect(result.fields[0]?.enumValues).toEqual(["red", "green", "blue"]);
    expect(result.zodSchema.parse({ color: "red" })).toEqual({ color: "red" });
    expect(() => result.zodSchema.parse({ color: "yellow" })).toThrow();
  });

  it("handles required vs optional fields", () => {
    const result = jsonSchemaToZod({
      properties: {
        req: { type: "string" },
        opt: { type: "string", default: "fallback" },
      },
      required: ["req"],
    });
    expect(result.fields.find((f) => f.key === "req")?.required).toBe(true);
    expect(result.fields.find((f) => f.key === "opt")?.required).toBe(false);
    expect(result.zodSchema.parse({ req: "val" })).toEqual({ req: "val", opt: "fallback" });
  });

  it("handles $defs/$ref resolution", () => {
    const result = jsonSchemaToZod({
      properties: {
        mode: { $ref: "#/$defs/Mode" },
      },
      required: ["mode"],
      $defs: {
        Mode: { enum: ["fast", "slow"] },
      },
    });
    expect(result.fields[0]?.type).toBe("enum");
    expect(result.fields[0]?.enumValues).toEqual(["fast", "slow"]);
    expect(result.zodSchema.parse({ mode: "fast" })).toEqual({ mode: "fast" });
  });

  it("handles allOf resolution", () => {
    const result = jsonSchemaToZod({
      properties: {
        level: {
          allOf: [{ $ref: "#/$defs/Level" }],
          default: "medium",
        },
      },
      $defs: {
        Level: { enum: ["low", "medium", "high"] },
      },
    });
    expect(result.fields[0]?.type).toBe("enum");
    expect(result.fields[0]?.defaultValue).toBe("medium");
    expect(result.defaults.level).toBe("medium");
    expect(result.zodSchema.parse({})).toEqual({ level: "medium" });
  });

  it("detects decimal string as number (type: string with numeric constraints)", () => {
    const result = jsonSchemaToZod({
      properties: {
        price: { type: "string", minimum: 0, maximum: 1000 },
      },
      required: ["price"],
    });
    expect(result.fields[0]?.type).toBe("number");
    expect(result.zodSchema.parse({ price: "42.5" })).toEqual({ price: 42.5 });
  });

  it("detects string with format: decimal as number", () => {
    const result = jsonSchemaToZod({
      properties: {
        rate: { type: "string", format: "decimal" },
      },
      required: ["rate"],
    });
    expect(result.fields[0]?.type).toBe("number");
  });

  it("preserves default values in result", () => {
    const result = jsonSchemaToZod({
      properties: {
        threshold: { type: "number", default: 5.0 },
        label: { type: "string", default: "default" },
      },
    });
    expect(result.defaults).toEqual({ threshold: 5.0, label: "default" });
  });

  it("applies exclusiveMinimum and exclusiveMaximum", () => {
    const result = jsonSchemaToZod({
      properties: {
        value: { type: "number", exclusiveMinimum: 0, exclusiveMaximum: 100 },
      },
      required: ["value"],
    });
    expect(result.fields[0]?.exclusiveMinimum).toBe(0);
    expect(result.fields[0]?.exclusiveMaximum).toBe(100);
    expect(() => result.zodSchema.parse({ value: 0 })).toThrow();
    expect(() => result.zodSchema.parse({ value: 100 })).toThrow();
    expect(result.zodSchema.parse({ value: 50 })).toEqual({ value: 50 });
  });

  it("uses title for label when provided", () => {
    const result = jsonSchemaToZod({
      properties: {
        my_field: { type: "string", title: "My Custom Label" },
      },
      required: ["my_field"],
    });
    expect(result.fields[0]?.label).toBe("My Custom Label");
  });

  it("humanizes key for label when title is absent", () => {
    const result = jsonSchemaToZod({
      properties: {
        some_field_name: { type: "string" },
      },
      required: ["some_field_name"],
    });
    expect(result.fields[0]?.label).toBe("Some Field Name");
  });
});
