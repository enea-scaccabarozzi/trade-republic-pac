import { SchemaField } from "@/components/wizard/schema-field";
import type { FieldMeta } from "@/lib/schema-to-zod";
import { cn } from "@/lib/utils";

export interface SchemaFormProps {
  fields: FieldMeta[];
  values: Record<string, unknown>;
  onParamChange: (key: string, value: unknown) => void;
  className?: string;
}

export function SchemaForm({ fields, values, onParamChange, className }: SchemaFormProps) {
  if (fields.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">This strategy has no configurable parameters.</p>
    );
  }

  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2", className)}>
      {fields.map((meta) => (
        <div key={meta.key} className={meta.description.length > 80 ? "col-span-full" : ""}>
          <SchemaField
            meta={meta}
            value={values[meta.key]}
            onChange={(v) => onParamChange(meta.key, v)}
          />
        </div>
      ))}
    </div>
  );
}
