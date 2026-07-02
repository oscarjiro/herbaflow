import { useRef, useState } from "react";
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
import { useChunkedValidate } from "@/hooks/useChunkedValidate";
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
  const hasInput = text.trim().length > 0;
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

  // Distinct entry count: used for the progress label and as the actual inputs to the API.
  const distinctCount = inputCount - duplicateCount;

  const { mutation: validate, progress } = useChunkedValidate<{ value: string }, ResolvedCompound>({
    validateChunk: async (inputs) => {
      const res = await validateCompounds({ body: { inputs } });
      const data = res.data as unknown as ValidateResponse;
      return { resolved: data?.resolved ?? [], failed: data?.failed ?? [] };
    },
    onSuccess: (data) => {
      setResolved(data.resolved);
      setFailed(data.failed);
      if (!showAddButton && data.resolved.length > 0) {
        onResolved(data.resolved);
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
          disabled={validate.isPending || disabled || mustAddValidatedBatch || !hasInput}
          title={
            mustAddValidatedBatch ? "Add the validated batch before validating again." : undefined
          }
          onClickAsync={() =>
            validate.mutateAsync(text.split("\n").map((l) => ({ value: l }))).then(() => undefined)
          }
        >
          Validate
        </StatefulButton>

        {validate.isPending && (
          <ManualValidateProgress kind="compound" entryCount={distinctCount} progress={progress} />
        )}

        <RemovableChipList
          overflowKind="compounds"
          items={resolved}
          getKey={(r) => r.compound_id}
          getLabel={(r) =>
            `${r.canonical_name ?? r.compound_id}${
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

        {(resolved.length > 0 || failed.length > 0 || hasInput) && (
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
