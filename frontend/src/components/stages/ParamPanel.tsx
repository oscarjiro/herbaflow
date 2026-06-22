/**
 * ParamPanel — collapsible panel for editing pipeline stage parameters.
 *
 * - Pre-populates from `params` (the frozen/overridden values on the run).
 * - Shows description + "(default X, recommended lo–hi)" hint per field.
 * - Redo button arms only when at least one value differs from `params` AND
 *   all values are within hard bounds (E7 rule).
 * - Out-of-hard-range values show an inline error message and block Redo.
 * - Values outside the *recommended* band are allowed — never blocked.
 * - On Redo, calls `onRedo` with only the changed values.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { ADME_BOOLEAN_PARAMS, ADME_NUMERIC_PARAMS } from "../../contract";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { cn } from "@/lib/cn";
import { humanizeLabel, humanizeValue } from "../../contract/labels";

function ParamInfo({ description, label }: { description?: string; label: string }) {
  if (!description) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`About ${label}`}
          className="text-hf-fg-4 hover:text-hf-fg-2 inline-flex"
        >
          <Info className="size-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{description}</TooltipContent>
    </Tooltip>
  );
}

type ScalarParamValue = number | boolean | string;
type ParamValue = ScalarParamValue | string[];

export type ParamMeta = {
  default: ParamValue;
  min: number | undefined;
  minExclusive: boolean;
  max: number | undefined;
  recommended_min: number | undefined;
  recommended_max: number | undefined;
  /** Allowed values for enum (select) params; undefined for free numeric/boolean params. */
  enum?: (number | string)[] | undefined;
  description: string;
};

export function ParamPanel<TValue extends ParamValue = ScalarParamValue>({
  params,
  meta,
  onRedo,
  onChange,
  hideRedo = false,
  disabled = false,
  numericKeys = ADME_NUMERIC_PARAMS,
  booleanKeys = ADME_BOOLEAN_PARAMS,
  selectKeys = [],
  arrayKeys = [],
  title = "ADME parameters",
}: {
  params: Record<string, TValue>;
  meta: Record<string, ParamMeta>;
  onRedo: (changed: Record<string, TValue>) => void;
  /** Collect-mode: called whenever the set of changed values changes. */
  onChange?: (changed: Record<string, number | boolean | string | string[]>) => void;
  /** When true, hides the Redo button (use in collect-mode panels). */
  hideRedo?: boolean;
  disabled?: boolean;
  /** Ordered numeric param keys to render (defaults to the ADME set). */
  numericKeys?: readonly string[];
  /** Ordered boolean param keys to render (defaults to the ADME set). */
  booleanKeys?: readonly string[];
  /** Ordered enum param keys to render as a <select> of their meta.enum (default none). */
  selectKeys?: readonly string[];
  /** Ordered enum-array param keys to render as checkbox groups (default none). */
  arrayKeys?: readonly string[];
  /** Collapsible panel title. */
  title?: string;
}) {
  const [open, setOpen] = useState(false);

  // Local editable state (string for number inputs, boolean for checkboxes)
  const [localStr, setLocalStr] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const key of Object.keys(meta)) {
      const v = params[key];
      if (v !== undefined && !Array.isArray(v)) init[key] = String(v);
    }
    return init;
  });

  const [localArrays, setLocalArrays] = useState<Record<string, string[]>>(() => {
    const init: Record<string, string[]> = {};
    for (const key of arrayKeys) {
      const v = params[key];
      if (Array.isArray(v)) {
        init[key] = v.map(String);
        continue;
      }
      const fallback = meta[key]?.default;
      if (Array.isArray(fallback)) init[key] = fallback.map(String);
    }
    return init;
  });

  // Compute hard-bound violations per field
  const violations: Record<string, string> = {};
  for (const key of numericKeys) {
    const m = meta[key];
    if (!m) continue;
    const raw = localStr[key];
    if (raw === undefined || raw === "") continue;
    const n = Number(raw);
    if (isNaN(n)) {
      violations[key] = "Must be a number";
      continue;
    }
    if (m.min !== undefined) {
      const belowMin = m.minExclusive ? n <= m.min : n < m.min;
      if (belowMin) {
        violations[key] = m.minExclusive
          ? `Must be greater than ${m.min}`
          : `Below minimum (${m.min})`;
        continue;
      }
    }
    if (m.max !== undefined && n > m.max) {
      violations[key] = `Exceeds maximum (${m.max})`;
    }
  }

  const hasViolations = Object.keys(violations).length > 0;

  // Compute whether any value differs from the frozen params
  const getChanged = useCallback((): Record<string, TValue> => {
    const changed: Record<string, TValue> = {};
    for (const key of numericKeys) {
      const frozen = params[key];
      const raw = localStr[key];
      if (raw === undefined) continue;
      const n = Number(raw);
      if (!isNaN(n) && n !== frozen) {
        changed[key] = n as TValue;
      }
    }
    for (const key of booleanKeys) {
      const frozen = params[key];
      const raw = localStr[key];
      if (raw === undefined) continue;
      const b = raw === "true";
      if (b !== frozen) {
        changed[key] = b as TValue;
      }
    }
    for (const key of selectKeys) {
      const frozen = params[key];
      const raw = localStr[key];
      if (raw === undefined) continue;
      // Recover the native enum value (number or string) from its string form.
      const options = meta[key]?.enum ?? [];
      const value = options.find((o) => String(o) === raw) ?? raw;
      if (value !== frozen) {
        changed[key] = value as TValue;
      }
    }
    for (const key of arrayKeys) {
      const frozen = Array.isArray(params[key]) ? params[key].map(String) : [];
      const current = localArrays[key] ?? [];
      const sameLength = frozen.length === current.length;
      const sameValues = sameLength && frozen.every((value, index) => value === current[index]);
      if (!sameValues) {
        changed[key] = current as TValue;
      }
    }
    return changed;
  }, [params, localStr, localArrays, numericKeys, booleanKeys, selectKeys, arrayKeys, meta]);

  const changed = getChanged();
  const hasChanges = Object.keys(changed).length > 0;
  const redoEnabled = hasChanges && !hasViolations && !disabled;

  // Collect-mode: fire onChange whenever the changed set itself changes.
  // Keyed on a stable serialization to avoid infinite render loops.
  const changedJson = JSON.stringify(changed);
  const onChangePrev = useRef<string | null>(null);
  useEffect(() => {
    if (!onChange) return;
    if (changedJson === onChangePrev.current) return;
    onChangePrev.current = changedJson;
    onChange(changed as Record<string, number | boolean | string | string[]>);
  }, [changedJson, onChange]);

  function handleNumericChange(key: string, value: string) {
    setLocalStr((s) => ({ ...s, [key]: value }));
  }

  function handleBooleanChange(key: string, checked: boolean) {
    setLocalStr((s) => ({ ...s, [key]: String(checked) }));
  }

  function handleSelectChange(key: string, value: string) {
    setLocalStr((s) => ({ ...s, [key]: value }));
  }

  function handleArrayToggle(key: string, value: string, checked: boolean) {
    setLocalArrays((state) => {
      const current = state[key] ?? [];
      const next = checked ? [...current, value] : current.filter((entry) => entry !== value);
      const optionOrder = meta[key]?.enum?.map(String) ?? [];
      return {
        ...state,
        [key]:
          optionOrder.length > 0
            ? optionOrder.filter((option) => next.includes(option))
            : Array.from(new Set(next)),
      };
    });
  }

  function handleRedo() {
    if (!redoEnabled) return;
    onRedo(getChanged());
  }

  return (
    <TooltipProvider>
    <Card className="w-full">
      <CardHeader className="pb-2">
        <button
          type="button"
          className="flex w-full items-center gap-2 text-left"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="text-muted-foreground text-xs">{open ? "▾" : "▸"}</span>
          <CardTitle className="text-sm">{title}</CardTitle>
        </button>
      </CardHeader>

      {open && (
        <CardContent className="flex flex-col gap-4 pt-0">
          {numericKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const err = violations[key];
            const label = humanizeLabel(key);
            const recHint =
              m.recommended_min !== undefined && m.recommended_max !== undefined
                ? `, recommended ${m.recommended_min}–${m.recommended_max}`
                : "";
            return (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex items-center gap-1">
                  <Label htmlFor={`param-${key}`}>{label}</Label>
                  <ParamInfo description={m.description} label={label} />
                </div>
                <p className="text-muted-foreground/70 text-xs">
                  (default {String(m.default)}
                  {recHint})
                </p>
                <Input
                  id={`param-${key}`}
                  type="number"
                  aria-label={label}
                  value={localStr[key] ?? ""}
                  disabled={disabled}
                  onChange={(e) => handleNumericChange(key, e.target.value)}
                  aria-invalid={err ? true : undefined}
                  className={cn(err && "border-destructive")}
                />
                {err && (
                  <p className="text-destructive text-xs" role="alert">
                    {err}
                  </p>
                )}
              </div>
            );
          })}

          {booleanKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const label = humanizeLabel(key);
            return (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id={`param-${key}`}
                    aria-label={label}
                    checked={localStr[key] === "true"}
                    disabled={disabled}
                    onCheckedChange={(checked) => handleBooleanChange(key, checked === true)}
                  />
                  <Label htmlFor={`param-${key}`}>{label}</Label>
                  <ParamInfo description={m.description} label={label} />
                </div>
              </div>
            );
          })}

          {selectKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const options = m.enum ?? [];
            const label = humanizeLabel(key);
            return (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex items-center gap-1">
                  <Label htmlFor={`param-${key}`}>{label}</Label>
                  <ParamInfo description={m.description} label={label} />
                </div>
                <p className="text-muted-foreground/70 text-xs">
                  (default {humanizeValue(String(m.default))})
                </p>
                <Select
                  value={localStr[key] ?? String(m.default)}
                  disabled={disabled}
                  onValueChange={(value) => handleSelectChange(key, value)}
                >
                  <SelectTrigger id={`param-${key}`} aria-label={label} className="w-full">
                    <SelectValue>{humanizeValue(localStr[key] ?? String(m.default))}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {options.map((o) => (
                      <SelectItem key={String(o)} value={String(o)}>
                        {humanizeValue(String(o))}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            );
          })}

          {arrayKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const options = m.enum?.map(String) ?? [];
            const selected = localArrays[key] ?? [];
            const defaultLabel = Array.isArray(m.default)
              ? m.default.map((value) => humanizeValue(String(value))).join(", ")
              : String(m.default);
            const label = humanizeLabel(key);
            return (
              <div key={key} className="flex flex-col gap-2">
                <div className="flex items-center gap-1">
                  <Label>{label}</Label>
                  <ParamInfo description={m.description} label={label} />
                </div>
                <p className="text-muted-foreground/70 text-xs">(default {defaultLabel})</p>
                <div className="flex flex-col gap-2">
                  {options.map((option) => {
                    const id = `param-${key}-${option.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
                    const label = humanizeValue(option);
                    return (
                      <div key={option} className="flex items-center gap-2">
                        <Checkbox
                          id={id}
                          aria-label={label}
                          checked={selected.includes(option)}
                          disabled={disabled}
                          onCheckedChange={(checked) =>
                            handleArrayToggle(key, option, checked === true)
                          }
                        />
                        <Label htmlFor={id}>{label}</Label>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {!hideRedo && (
            <Button
              type="button"
              disabled={!redoEnabled}
              onClick={handleRedo}
              aria-label="Redo from this stage with changed parameters"
              className="self-start"
            >
              Redo
            </Button>
          )}
        </CardContent>
      )}
    </Card>
    </TooltipProvider>
  );
}
