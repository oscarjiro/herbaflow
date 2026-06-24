import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { validateCompounds } from "../api/sdk.gen";
import type { FailedInput, ResolvedCompound, ValidateResponse } from "../api/types.gen";
import type { Problem } from "../lib/problem";
import { notifyError } from "../lib/toast";
import { FailedInputList } from "./FailedInputList";
import { RemovableChipList } from "./RemovableChipList";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { LineNumberedTextarea } from "@/components/ui/line-numbered-textarea";
import { ManualValidateProgress } from "@/components/ui/ManualValidateProgress";
import { ManualEntrySummary, nonEmptyLineCount } from "@/components/ui/ManualEntrySummary";
import { StatefulButton } from "@/components/ui/StatefulButton";
import { MAX_COMPOUNDS } from "@/contract";

/**
 * Reusable compound validate box: line-numbered editor + Validate button +
 * resolved/failed lists.
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

  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const textareaId = `compound-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`;

  // Build 1-based line -> reason map from the failed list.
  const errorLines: ReadonlyMap<number, string> = new Map(
    failed
      .filter((f): f is FailedInput & { line: number } => typeof f.line === "number")
      .map((f) => [f.line, f.reason]),
  );

  // Repeated non-empty input lines, for the at-a-glance summary roll-up.
  const inputCount = nonEmptyLineCount(text);
  const mustAddValidatedBatch = showAddButton === true && resolved.length > 0;
  const duplicateCount = (() => {
    const seen = new Set<string>();
    let dup = 0;
    for (const raw of text.split("\n")) {
      const v = raw.trim();
      if (!v) continue;
      if (seen.has(v)) dup += 1;
      else seen.add(v);
    }
    return dup;
  })();

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
    onError: (error) => {
      notifyError(error as Problem);
    },
  });

  function handleAdd() {
    onResolved(resolved);
    setResolved([]);
    setFailed([]);
    setText("");
  }

  return (
    <Card className="gap-3 py-4">
      <CardContent className="flex flex-col gap-3">
        <Label htmlFor={textareaId}>{label}</Label>
        <LineNumberedTextarea
          ref={editorRef}
          id={textareaId}
          aria-label={label}
          value={text}
          onChange={setText}
          placeholder="One SMILES or InChIKey per line"
          disabled={disabled}
          rows={3}
          errorLines={errorLines}
        />
        <StatefulButton
          variant="secondary"
          size="sm"
          successDuration={0}
          className="w-full"
          wrapperClassName="w-full"
          disabled={validate.isPending || disabled || mustAddValidatedBatch}
          title={
            mustAddValidatedBatch ? "Add the validated batch before validating again." : undefined
          }
          onClickAsync={() => validate.mutateAsync().then(() => undefined)}
        >
          Validate
        </StatefulButton>

        {validate.isPending && <ManualValidateProgress kind="compound" entryCount={inputCount} />}

        <RemovableChipList
          overflowKind="compounds"
          items={resolved}
          getKey={(r) => r.compound_id}
          getLabel={(r) =>
            `${r.canonical_name ?? r.canonical_key}${
              r.validation_status === "structure_only" ? " (structure only)" : ""
            }`
          }
          onRemove={(r) =>
            setResolved((current) => current.filter((x) => x.compound_id !== r.compound_id))
          }
          ariaLabel="Resolved compounds"
        />

        <FailedInputList
          failed={failed}
          text={text}
          editorRef={editorRef}
          controlsId={`${textareaId}-failed`}
        />

        {(resolved.length > 0 || failed.length > 0 || text.trim().length > 0) && (
          <ManualEntrySummary
            validCount={resolved.length}
            invalidCount={failed.length}
            duplicateCount={duplicateCount}
            current={inputCount}
            max={MAX_COMPOUNDS}
            onClear={() => {
              setText("");
              setResolved([]);
              setFailed([]);
            }}
          />
        )}

        {showAddButton && resolved.length > 0 && (
          <Button type="button" size="sm" onClick={handleAdd}>
            Add
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
