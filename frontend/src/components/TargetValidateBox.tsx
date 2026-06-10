import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { validateTargets } from "../api/sdk.gen";
import type { FailedInput, ResolvedTarget, ValidateTargetsResponse } from "../api/types.gen";

/**
 * Reusable target validate box: textarea + Validate button + resolved/failed lists.
 *
 * Props:
 *  - onResolved: called with resolved targets when the user confirms (see showAddButton)
 *  - label: aria-label and visible label for the textarea (default "Add targets")
 *  - disabled: when true, the textarea and button are both disabled
 *  - showAddButton: when true, renders an "Add" button after resolved results; clicking it
 *    calls onResolved(resolved) and clears state. When false/absent (default), onResolved
 *    is called immediately on successful validation (SetupView behaviour).
 */
export function TargetValidateBox({
  onResolved,
  label = "Add targets",
  disabled,
  showAddButton,
}: {
  onResolved: (resolved: ResolvedTarget[]) => void;
  label?: string;
  disabled?: boolean;
  showAddButton?: boolean;
}) {
  const [text, setText] = useState("");
  const [resolved, setResolved] = useState<ResolvedTarget[]>([]);
  const [failed, setFailed] = useState<FailedInput[]>([]);

  const validate = useMutation({
    mutationFn: async () => {
      const inputs = text
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((value) => ({ value }));
      const res = await validateTargets({ body: { inputs } });
      return res.data as unknown as ValidateTargetsResponse;
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
    <div className="target-validate-box">
      <label htmlFor={`target-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`}>
        {label}
      </label>
      <textarea
        id={`target-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`}
        aria-label={label}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="One gene symbol or UniProt accession per line"
        disabled={disabled}
      />
      <button disabled={validate.isPending || disabled} onClick={() => validate.mutate()}>
        Validate
      </button>

      {resolved.length > 0 && (
        <ul aria-label="Resolved targets">
          {resolved.map((r) => (
            <li key={r.target_id}>{r.gene_symbol ?? r.uniprot_accession ?? r.canonical_key}</li>
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
