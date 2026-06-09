import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { validateCompounds } from "../api/sdk.gen";
import type { FailedInput, ResolvedCompound, ValidateResponse } from "../api/types.gen";

/**
 * Reusable compound validate box: textarea + Validate button + resolved/failed lists.
 *
 * Props:
 *  - onResolved: called with resolved compounds when the user confirms (see showAddButton)
 *  - label: aria-label and visible label for the textarea (default "Manual compounds")
 *  - disabled: when true, the textarea and button are both disabled
 *  - showAddButton: when true, renders an "Add" button after resolved results; clicking it
 *    calls onResolved(resolved) and clears state. When false/absent (default), onResolved
 *    is called immediately on successful validation (SetupView behaviour).
 */
export function CompoundValidateBox({
  onResolved,
  label = "Manual compounds",
  disabled,
  showAddButton,
}: {
  onResolved: (resolved: ResolvedCompound[]) => void;
  label?: string;
  disabled?: boolean;
  showAddButton?: boolean;
}) {
  const [text, setText] = useState("");
  const [resolved, setResolved] = useState<ResolvedCompound[]>([]);
  const [failed, setFailed] = useState<FailedInput[]>([]);

  const validate = useMutation({
    mutationFn: async () => {
      const inputs = text
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((value) => ({ value }));
      const res = await validateCompounds({ body: { inputs } });
      return res.data as unknown as ValidateResponse;
    },
    onSuccess: (data) => {
      const resolvedList = data?.resolved ?? [];
      setResolved(resolvedList);
      setFailed(data?.failed ?? []);
      if (!showAddButton && resolvedList.length > 0) {
        onResolved(resolvedList);
      }
    },
  });

  function handleAdd() {
    onResolved(resolved);
    setResolved([]);
    setFailed([]);
    setText("");
  }

  return (
    <div className="compound-validate-box">
      <label htmlFor={`compound-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`}>
        {label}
      </label>
      <textarea
        id={`compound-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`}
        aria-label={label}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="One SMILES or InChIKey per line"
        disabled={disabled}
      />
      <button disabled={validate.isPending || disabled} onClick={() => validate.mutate()}>
        Validate
      </button>

      {resolved.length > 0 && (
        <ul aria-label="Resolved compounds">
          {resolved.map((r) => (
            <li key={r.compound_id}>
              {r.canonical_name ?? r.canonical_key}
              {r.validation_status === "structure_only" && " (structure only)"}
            </li>
          ))}
        </ul>
      )}

      {failed.length > 0 && (
        <ul aria-label="Failed inputs">
          {failed.map((f) => (
            <li key={f.value}>
              {f.value}: {f.reason}
            </li>
          ))}
        </ul>
      )}

      {showAddButton && resolved.length > 0 && <button onClick={handleAdd}>Add</button>}
    </div>
  );
}
