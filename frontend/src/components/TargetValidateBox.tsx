import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { validateTargets } from "../api/sdk.gen";
import type { FailedInput, ResolvedTarget, ValidateTargetsResponse } from "../api/types.gen";
import { humanizeProblem } from "../lib/problem";
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
  const [failedExpanded, setFailedExpanded] = useState(false);

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
      setFailedExpanded(false);
      if (!showAddButton && resolvedList.length > 0) {
        onResolved(resolvedList);
      }
    },
    onError: (error) => {
      toast.error(humanizeProblem(error as Parameters<typeof humanizeProblem>[0]));
    },
  });

  function handleAdd() {
    onResolved(resolved);
    setResolved([]);
    setFailed([]);
    setText("");
  }

  /**
   * Best-effort focus + caret jump to the start of the given 1-based line.
   * Computed by summing char lengths of all preceding lines + their newlines.
   * No-ops silently in jsdom (where setSelectionRange may not move the caret).
   */
  function jumpToLine(lineNum: number) {
    const el = editorRef.current;
    if (!el) return;
    const lines = text.split("\n");
    let offset = 0;
    for (let i = 0; i < lineNum - 1 && i < lines.length; i++) {
      offset += (lines[i]?.length ?? 0) + 1; // +1 for the newline
    }
    try {
      el.focus();
      el.setSelectionRange(offset, offset);
    } catch {
      // jsdom or older browsers may not support this — no-op
    }
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

        {failed.length > 0 && (
          <div className="flex flex-col gap-1">
            <button
              type="button"
              className="text-destructive w-fit text-xs font-medium underline-offset-2 hover:underline"
              onClick={() => setFailedExpanded((v) => !v)}
              aria-expanded={failedExpanded}
            >
              {failed.length} invalid input{failed.length !== 1 ? "s" : ""}
            </button>
            {failedExpanded && (
              <ul aria-label="Failed inputs" className="flex flex-col gap-1">
                {failed.map((f) => (
                  <li key={f.value} className="list-none text-xs [color:var(--hf-fg-3)]">
                    <button
                      type="button"
                      className="contents"
                      onClick={() => {
                        if (typeof f.line === "number") jumpToLine(f.line);
                      }}
                      aria-label={
                        typeof f.line === "number" ? `Go to line ${f.line}: ${f.value}` : undefined
                      }
                    >
                      <Badge variant="destructive" className="mr-1.5">
                        {typeof f.line === "number" ? `Line ${f.line}: ` : ""}
                        {f.value}
                      </Badge>
                    </button>
                    <span>{f.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
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
