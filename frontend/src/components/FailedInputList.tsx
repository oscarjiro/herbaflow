import { useState } from "react";
import type { RefObject } from "react";
import type { FailedInput } from "../api/types.gen";
import { jumpToLine } from "../lib/jump-to-line";
import { Badge } from "@/components/ui/badge";

/**
 * Collapsed/expanded list of validation failures.
 *
 * Owns its own `failedExpanded` toggle state and builds the 1-based
 * line→reason map internally from `failed`.
 *
 * Props:
 *  - failed: the failed-input rows returned by the validate endpoint
 *  - text: the current textarea value (passed to jumpToLine)
 *  - editorRef: ref to the textarea DOM node (passed to jumpToLine)
 *  - controlsId: value for aria-controls on the toggle button; must
 *    match the id of the expanded <ul>. Convention used by both boxes:
 *    `${textareaId}-failed`.
 */
export function FailedInputList({
  failed,
  text,
  editorRef,
  controlsId,
}: {
  failed: FailedInput[];
  text: string;
  editorRef: RefObject<HTMLTextAreaElement | null>;
  controlsId: string;
}) {
  const [failedExpanded, setFailedExpanded] = useState(false);

  if (failed.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        className="text-destructive w-fit text-xs font-medium underline-offset-2 hover:underline"
        onClick={() => setFailedExpanded((v) => !v)}
        aria-expanded={failedExpanded}
        aria-controls={controlsId}
      >
        {failed.length} invalid input{failed.length !== 1 ? "s" : ""}
      </button>
      {failedExpanded && (
        <ul id={controlsId} aria-label="Failed inputs" className="flex flex-col gap-1">
          {failed.map((f, i) => (
            <li
              key={`${f.line ?? "?"}-${f.value}-${i}`}
              className="list-none text-xs [color:var(--hf-fg-3)]"
            >
              <button
                type="button"
                className="contents"
                onClick={() => {
                  if (typeof f.line === "number") jumpToLine(editorRef.current, text, f.line);
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
  );
}
