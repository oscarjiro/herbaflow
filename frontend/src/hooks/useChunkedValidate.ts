import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { FailedInput } from "@/api/types.gen";
import { distinctInputsWithOrigin } from "@/lib/validateInputs";

/**
 * Number of distinct entries sent per /…/validate request.
 *
 * Validation of a large paste (hundreds of gene symbols / SMILES) resolves each
 * distinct entry against an external API and can take minutes. The endpoint
 * returns one final response per request, so the only way to show HONEST
 * progress is to send the work in batches and report after each one. The
 * backend already batch-resolves within a request (bounded concurrency), so a
 * batch of this size keeps that parallelism while giving the user a real "X of
 * N" count rather than a spinner that looks frozen.
 */
export const VALIDATE_CHUNK_SIZE = 100;

export interface ChunkProgress {
  done: number;
  total: number;
}

export interface ChunkResult<R> {
  resolved: R[];
  failed: FailedInput[];
}

/**
 * Run /compounds/validate or /targets/validate over a large input list in
 * batches, accumulating results and exposing real progress.
 *
 * - Dedups + records each distinct entry's original textarea line via
 *   `distinctInputsWithOrigin` (the one dedup home).
 * - Sends the distinct entries in `VALIDATE_CHUNK_SIZE` batches, sequentially,
 *   updating `progress` after each batch.
 * - Remaps every failure's batch-local `line` back to the user's original line,
 *   so the failed list and jump-to-line point at the right row regardless of
 *   dedup or batching.
 *
 * `validateChunk` performs ONE request for a batch and returns its resolved +
 * failed arrays. `mutate`/`mutateAsync` take the raw per-line inputs.
 */
export function useChunkedValidate<I extends { value: string }, R>(opts: {
  validateChunk: (inputs: I[]) => Promise<ChunkResult<R>>;
  onSuccess?: (data: ChunkResult<R>) => void;
  onError?: (error: unknown) => void;
}) {
  const [progress, setProgress] = useState<ChunkProgress | null>(null);

  const mutation = useMutation<ChunkResult<R>, unknown, I[]>({
    mutationFn: async (rawInputs: I[]): Promise<ChunkResult<R>> => {
      const { items, lines } = distinctInputsWithOrigin(rawInputs);
      const total = items.length;
      setProgress({ done: 0, total });

      const resolved: R[] = [];
      const failed: FailedInput[] = [];
      for (let offset = 0; offset < items.length; offset += VALIDATE_CHUNK_SIZE) {
        const batch = items.slice(offset, offset + VALIDATE_CHUNK_SIZE);
        const res = await opts.validateChunk(batch);
        resolved.push(...res.resolved);
        for (const f of res.failed) {
          // Backend numbers `line` 1-based within the batch it received; map it
          // through the batch offset back to the original input line.
          const originLine =
            typeof f.line === "number" ? (lines[offset + f.line - 1] ?? f.line) : f.line;
          failed.push({ ...f, line: originLine });
        }
        setProgress({ done: Math.min(offset + batch.length, total), total });
      }
      return { resolved, failed };
    },
    onSuccess: opts.onSuccess,
    onError: opts.onError,
    onSettled: () => setProgress(null),
  });

  return { mutation, progress };
}
