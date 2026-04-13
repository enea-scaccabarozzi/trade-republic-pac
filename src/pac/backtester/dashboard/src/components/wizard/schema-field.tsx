import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { FieldMeta } from "@/lib/schema-to-zod";

export interface SchemaFieldProps {
  meta: FieldMeta;
  value: unknown;
  onChange: (value: unknown) => void;
}

function FieldInput({ meta, value, onChange }: SchemaFieldProps) {
  if (meta.type === "number" || meta.type === "integer") {
    return (
      <Input
        id={meta.key}
        type="number"
        step={meta.type === "integer" ? "1" : "any"}
        min={meta.minimum}
        max={meta.maximum}
        value={value as string}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (meta.type === "boolean") {
    return (
      <div className="flex items-center gap-2">
        <Switch
          id={meta.key}
          checked={value as boolean}
          onCheckedChange={(checked) => onChange(checked)}
        />
        <Label htmlFor={meta.key}>
          {meta.label}
          {meta.required && <span className="ml-1 text-destructive">*</span>}
        </Label>
      </div>
    );
  }
  if (meta.type === "enum") {
    return (
      <Select value={value as string} onValueChange={(val) => onChange(val)}>
        <SelectTrigger id={meta.key} className="w-full">
          <SelectValue placeholder={`Select ${meta.label.toLowerCase()}`} />
        </SelectTrigger>
        <SelectContent>
          {meta.enumValues?.map((val) => (
            <SelectItem key={val} value={val}>
              {val}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  return (
    <Input
      id={meta.key}
      type="text"
      value={value as string}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function SchemaField({ meta, value, onChange }: SchemaFieldProps) {
  return (
    <div className="space-y-2">
      {meta.type !== "boolean" && (
        <Label htmlFor={meta.key}>
          {meta.label}
          {meta.required && <span className="ml-1 text-destructive">*</span>}
        </Label>
      )}

      <FieldInput meta={meta} value={value} onChange={onChange} />

      {meta.description && <p className="text-xs text-muted-foreground">{meta.description}</p>}
    </div>
  );
}
