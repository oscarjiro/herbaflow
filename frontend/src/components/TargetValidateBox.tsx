import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { validateTargets } from "../api/sdk.gen";
import type { FailedInput, ResolvedTarget, ValidateTargetsResponse } from "../api/types.gen";
import type { Problem } from "../lib/problem";
import { notifyError } from "../lib/toast";
import { FailedInputList } from "./FailedInputList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { LineNumberedTextarea } from "@/components/ui/line-numbered-textarea";

/**
 * Reusable target validate box: line-numbered editor + Validate button +
 * resolved/failed lists.
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

  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const textareaId = `target-validate-box-${label.replace(/\s+/g, "-").toLowerCase()}`;

  // Build 1-based line -> reason map from the failed list.
  const errorLines: ReadonlyMap<number, string> = new Map(
    failed
      .filter((f): f is FailedInput & { line: number } => typeof f.line === "number")
      .map((f) => [f.line, f.reason]),
  );

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
          placeholder="One gene symbol or UniProt accession per line"
          disabled={disabled}
          rows={3}
          errorLines={errorLines}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={validate.isPending || disabled}
          onClick={() => validate.mutate()}
        >
          Validate
        </Button>

        {resolved.length > 0 && (
          <ul aria-label="Resolved targets" className="flex flex-wrap gap-1.5">
            {resolved.map((r) => (
              <li key={r.target_id} className="list-none">
                <Badge variant="secondary">
                  {r.gene_symbol ?? r.uniprot_accession ?? r.canonical_key}
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <FailedInputList
          failed={failed}
          text={text}
          editorRef={editorRef}
          controlsId={`${textareaId}-failed`}
        />

        {showAddButton && resolved.length > 0 && (
          <Button type="button" size="sm" onClick={handleAdd}>
            Add
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
