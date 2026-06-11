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

import { useState, useCallback } from "react";
import { ADME_BOOLEAN_PARAMS, ADME_NUMERIC_PARAMS } from "../../contract";

export type ParamMeta = {
  default: number | boolean | string;
  min: number | undefined;
  minExclusive: boolean;
  max: number | undefined;
  recommended_min: number | undefined;
  recommended_max: number | undefined;
  /** Allowed values for enum (select) params; undefined for free numeric/boolean params. */
  enum?: (number | string)[] | undefined;
  description: string;
};

export function ParamPanel({
  params,
  meta,
  onRedo,
  disabled = false,
  numericKeys = ADME_NUMERIC_PARAMS,
  booleanKeys = ADME_BOOLEAN_PARAMS,
  selectKeys = [],
  title = "ADME parameters",
}: {
  params: Record<string, number | boolean | string>;
  meta: Record<string, ParamMeta>;
  onRedo: (changed: Record<string, number | boolean | string>) => void;
  disabled?: boolean;
  /** Ordered numeric param keys to render (defaults to the ADME set). */
  numericKeys?: readonly string[];
  /** Ordered boolean param keys to render (defaults to the ADME set). */
  booleanKeys?: readonly string[];
  /** Ordered enum param keys to render as a <select> of their meta.enum (default none). */
  selectKeys?: readonly string[];
  /** Collapsible panel title. */
  title?: string;
}) {
  const [open, setOpen] = useState(true);

  // Local editable state (string for number inputs, boolean for checkboxes)
  const [localStr, setLocalStr] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const key of Object.keys(meta)) {
      const v = params[key];
      if (v !== undefined) init[key] = String(v);
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
  const getChanged = useCallback((): Record<string, number | boolean | string> => {
    const changed: Record<string, number | boolean | string> = {};
    for (const key of numericKeys) {
      const frozen = params[key];
      const raw = localStr[key];
      if (raw === undefined) continue;
      const n = Number(raw);
      if (!isNaN(n) && n !== frozen) {
        changed[key] = n;
      }
    }
    for (const key of booleanKeys) {
      const frozen = params[key];
      const raw = localStr[key];
      if (raw === undefined) continue;
      const b = raw === "true";
      if (b !== frozen) {
        changed[key] = b;
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
        changed[key] = value;
      }
    }
    return changed;
  }, [params, localStr, numericKeys, booleanKeys, selectKeys, meta]);

  const changed = getChanged();
  const hasChanges = Object.keys(changed).length > 0;
  const redoEnabled = hasChanges && !hasViolations && !disabled;

  function handleNumericChange(key: string, value: string) {
    setLocalStr((s) => ({ ...s, [key]: value }));
  }

  function handleBooleanChange(key: string, checked: boolean) {
    setLocalStr((s) => ({ ...s, [key]: String(checked) }));
  }

  function handleSelectChange(key: string, value: string) {
    setLocalStr((s) => ({ ...s, [key]: value }));
  }

  function handleRedo() {
    if (!redoEnabled) return;
    onRedo(getChanged());
  }

  return (
    <div className="param-panel">
      <button
        type="button"
        className="hf-btn hf-btn-ghost param-panel__toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "▾" : "▸"} {title}
      </button>

      {open && (
        <div className="param-panel__body">
          {numericKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const err = violations[key];
            const recHint =
              m.recommended_min !== undefined && m.recommended_max !== undefined
                ? `, recommended ${m.recommended_min}–${m.recommended_max}`
                : "";
            return (
              <div key={key} className="param-row">
                <label htmlFor={`param-${key}`} className="param-row__label">
                  {key}
                </label>
                <p className="param-row__description">
                  {m.description}
                  <span className="param-row__hint">
                    {" "}
                    (default {String(m.default)}
                    {recHint})
                  </span>
                </p>
                <input
                  id={`param-${key}`}
                  type="number"
                  aria-label={key}
                  value={localStr[key] ?? ""}
                  disabled={disabled}
                  onChange={(e) => handleNumericChange(key, e.target.value)}
                  className={err ? "param-input param-input--error" : "param-input"}
                />
                {err && <p className="param-error">{err}</p>}
              </div>
            );
          })}

          {booleanKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            return (
              <div key={key} className="param-row">
                <label className="param-row__label">
                  <input
                    type="checkbox"
                    aria-label={key}
                    checked={localStr[key] === "true"}
                    disabled={disabled}
                    onChange={(e) => handleBooleanChange(key, e.target.checked)}
                  />{" "}
                  {key}
                </label>
                <p className="param-row__description">{m.description}</p>
              </div>
            );
          })}

          {selectKeys.map((key) => {
            const m = meta[key];
            if (!m) return null;
            const options = m.enum ?? [];
            return (
              <div key={key} className="param-row">
                <label htmlFor={`param-${key}`} className="param-row__label">
                  {key}
                </label>
                <p className="param-row__description">
                  {m.description}
                  <span className="param-row__hint"> (default {String(m.default)})</span>
                </p>
                <select
                  id={`param-${key}`}
                  aria-label={key}
                  value={localStr[key] ?? String(m.default)}
                  disabled={disabled}
                  onChange={(e) => handleSelectChange(key, e.target.value)}
                  className="param-input"
                >
                  {options.map((o) => (
                    <option key={String(o)} value={String(o)}>
                      {String(o)}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}

          <button
            type="button"
            className="hf-btn hf-btn-primary"
            disabled={!redoEnabled}
            onClick={handleRedo}
            aria-label="Redo from this stage with changed parameters"
          >
            Redo
          </button>
        </div>
      )}
    </div>
  );
}
