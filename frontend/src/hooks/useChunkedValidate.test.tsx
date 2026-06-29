import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import type { FailedInput } from "@/api/types.gen";
import { useChunkedValidate, VALIDATE_CHUNK_SIZE, type ChunkResult } from "./useChunkedValidate";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

interface Resolved {
  id: string;
}

// A fake per-batch validator: fails any value starting with "BAD" (carrying its
// batch-local 1-based line, exactly as the backend would) and resolves the rest.
function makeChunkValidator(batchSizes: number[]) {
  return async (inputs: { value: string }[]): Promise<ChunkResult<Resolved>> => {
    batchSizes.push(inputs.length);
    const resolved: Resolved[] = [];
    const failed: FailedInput[] = [];
    inputs.forEach((it, i) => {
      if (it.value.startsWith("BAD")) {
        failed.push({ value: it.value, reason: "bad", line: i + 1 });
      } else {
        resolved.push({ id: it.value });
      }
    });
    return { resolved, failed };
  };
}

describe("useChunkedValidate", () => {
  test("dedups, drops blanks, and remaps failure lines to the original textarea line", async () => {
    const batchSizes: number[] = [];
    const { result } = renderHook(
      () =>
        useChunkedValidate<{ value: string }, Resolved>({
          validateChunk: makeChunkValidator(batchSizes),
        }),
      { wrapper },
    );

    // Lines: 1 GOOD1, 2 blank, 3 BADX, 4 GOOD1(dup), 5 GOOD2
    const raw = [
      { value: "GOOD1" },
      { value: "" },
      { value: "BADX" },
      { value: "GOOD1" },
      { value: "GOOD2" },
    ];

    let out!: ChunkResult<Resolved>;
    await act(async () => {
      out = await result.current.mutation.mutateAsync(raw);
    });

    expect(batchSizes).toEqual([3]); // three distinct entries -> one batch
    expect(out.resolved).toEqual([{ id: "GOOD1" }, { id: "GOOD2" }]);
    // BADX is the 2nd distinct entry; its batch-local line 2 maps back to original line 3.
    expect(out.failed).toEqual([{ value: "BADX", reason: "bad", line: 3 }]);
    expect(result.current.progress).toBeNull(); // cleared on settle
  });

  test("splits into batches and offsets each batch's failure lines correctly", async () => {
    const batchSizes: number[] = [];
    const { result } = renderHook(
      () =>
        useChunkedValidate<{ value: string }, Resolved>({
          validateChunk: makeChunkValidator(batchSizes),
        }),
      { wrapper },
    );

    // One past the batch boundary; fail the first item of EACH batch.
    const n = VALIDATE_CHUNK_SIZE + 2;
    const raw = Array.from({ length: n }, (_, i) => ({
      value: i === 0 || i === VALIDATE_CHUNK_SIZE ? `BAD${i}` : `G${i}`,
    }));

    let out!: ChunkResult<Resolved>;
    await act(async () => {
      out = await result.current.mutation.mutateAsync(raw);
    });

    expect(batchSizes).toEqual([VALIDATE_CHUNK_SIZE, 2]); // sequential batches
    // Failures at original lines 1 and CHUNK_SIZE+1 (the first row of each batch).
    expect(out.failed.map((f) => f.line)).toEqual([1, VALIDATE_CHUNK_SIZE + 1]);
    expect(out.resolved).toHaveLength(n - 2);
  });
});
