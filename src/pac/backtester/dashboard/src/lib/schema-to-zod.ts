import { z } from "zod";

/** Metadata extracted from a JSON Schema property for rendering. */
export interface FieldMeta {
  key: string;
  type: "number" | "integer" | "string" | "boolean" | "enum";
  label: string;
  description: string;
  defaultValue: unknown;
  required: boolean;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  enumValues?: string[];
}

export interface SchemaParseResult {
  zodSchema: z.ZodObject<Record<string, z.ZodTypeAny>>;
  fields: FieldMeta[];
  defaults: Record<string, unknown>;
}

export function jsonSchemaToZod(schema: Record<string, unknown>): SchemaParseResult {
  const properties = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const requiredKeys = new Set((schema.required ?? []) as string[]);
  const defs = (schema.$defs ?? {}) as Record<string, Record<string, unknown>>;

  const zodFields: Record<string, z.ZodTypeAny> = {};
  const fields: FieldMeta[] = [];
  const defaults: Record<string, unknown> = {};

  for (const [key, prop] of Object.entries(properties)) {
    const meta = extractFieldMeta(key, prop, requiredKeys.has(key), defs);
    fields.push(meta);
    zodFields[key] = buildZodField(meta);
    if (meta.defaultValue !== undefined) {
      defaults[key] = meta.defaultValue;
    }
  }

  return {
    zodSchema: z.object(zodFields),
    fields,
    defaults,
  };
}

function resolveRef(
  prop: Record<string, unknown>,
  defs: Record<string, Record<string, unknown>>,
): Record<string, unknown> {
  if (prop.$ref && typeof prop.$ref === "string") {
    const refName = (prop.$ref as string).replace("#/$defs/", "");
    if (defs[refName]) {
      return { ...defs[refName], ...prop };
    }
  }
  if (prop.allOf && Array.isArray(prop.allOf)) {
    const resolved = (prop.allOf as Record<string, unknown>[]).map((entry) =>
      entry.$ref ? resolveRef(entry as Record<string, unknown>, defs) : entry,
    );
    return Object.assign({}, ...resolved, prop);
  }
  return prop;
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function detectFieldType(resolved: Record<string, unknown>): FieldMeta["type"] {
  if (resolved.enum) return "enum";
  if (resolved.type === "boolean") return "boolean";
  if (resolved.type === "integer") return "integer";
  if (resolved.type === "number" || (resolved.type === "string" && resolved.format === "decimal")) {
    return "number";
  }
  // Pydantic Decimal fields appear as type: "string" with numeric constraints
  if (
    resolved.type === "string" &&
    (resolved.minimum !== undefined ||
      resolved.maximum !== undefined ||
      resolved.exclusiveMinimum !== undefined ||
      resolved.exclusiveMaximum !== undefined ||
      (resolved as Record<string, unknown>).ge !== undefined ||
      (resolved as Record<string, unknown>).le !== undefined)
  ) {
    return "number";
  }
  return "string";
}

function extractFieldMeta(
  key: string,
  prop: Record<string, unknown>,
  required: boolean,
  defs: Record<string, Record<string, unknown>>,
): FieldMeta {
  const resolved = resolveRef(prop, defs);
  const type = detectFieldType(resolved);

  return {
    key,
    type,
    label: (resolved.title as string) ?? humanizeKey(key),
    description: (resolved.description as string) ?? "",
    defaultValue: resolved.default,
    required: required && resolved.default === undefined,
    minimum: (resolved.minimum ?? resolved.ge) as number | undefined,
    maximum: (resolved.maximum ?? resolved.le) as number | undefined,
    exclusiveMinimum: (resolved.exclusiveMinimum ?? resolved.gt) as number | undefined,
    exclusiveMaximum: (resolved.exclusiveMaximum ?? resolved.lt) as number | undefined,
    enumValues: resolved.enum as string[] | undefined,
  };
}

function buildZodField(meta: FieldMeta): z.ZodTypeAny {
  let schema: z.ZodTypeAny;

  switch (meta.type) {
    case "number": {
      let n = z.coerce.number();
      if (meta.minimum !== undefined) n = n.min(meta.minimum);
      if (meta.maximum !== undefined) n = n.max(meta.maximum);
      if (meta.exclusiveMinimum !== undefined) n = n.gt(meta.exclusiveMinimum);
      if (meta.exclusiveMaximum !== undefined) n = n.lt(meta.exclusiveMaximum);
      schema = n;
      break;
    }
    case "integer": {
      let n = z.coerce.number().int();
      if (meta.minimum !== undefined) n = n.min(meta.minimum);
      if (meta.maximum !== undefined) n = n.max(meta.maximum);
      schema = n;
      break;
    }
    case "boolean":
      schema = z.boolean();
      break;
    case "enum":
      schema = z.enum(meta.enumValues as [string, ...string[]]);
      break;
    default:
      schema = z.string().min(1);
      break;
  }

  if (!meta.required && meta.defaultValue !== undefined) {
    schema = schema.default(meta.defaultValue);
  }

  return schema;
}
