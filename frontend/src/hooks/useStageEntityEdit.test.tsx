import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getAnalysisOptions } from "../api/@tanstack/react-query.gen";
import * as sdk from "../api/sdk.gen";
import type { AnalysisRead } from "../api/types.gen";
import * as toastLib from "../lib/toast";
import { useStageEntityEdit } from "./useStageEntityEdit";

function makeRun(): AnalysisRead {
  return {
    analysis_id: "a1",
    analysis_name: null,
    disease_id: "d1",
    mode: "guided",
    status: "stage_1_awaiting_approval",
    current_stage: 1,
    parameters: {},
    stage_results: {
      "1": {
        count: 2,
        compounds: [
          { compound_id: "C1", canonical_name: "Quercetin", tag: "computed" },
          { compound_id: "C2", canonical_name: "Kaempferol", tag: "computed" },
        ],
        state: "computed",
      },
    },
    stage_state: { "1": "computed" },
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
  } as unknown as AnalysisRead;
}

function wrapperFor(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useStageEntityEdit", () => {
  it("restores the cached run and shows a rollback toast when a compound remove fails", async () => {
    vi.spyOn(sdk, "editStage").mockRejectedValue({ title: "Edit failed" } as never);
    const notifyErrorSpy = vi.spyOn(toastLib, "notifyError").mockImplementation(() => {});

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const key = getAnalysisOptions({ path: { analysis_id: "a1" } }).queryKey;
    const run = makeRun();
    qc.setQueryData(key, run);

    const { result } = renderHook(
      () =>
        useStageEntityEdit({
          analysisId: "a1",
          stage: 1,
          entity: { singular: "compound", plural: "compounds" },
        }),
      { wrapper: wrapperFor(qc) },
    );

    await act(async () => {
      await result.current.mutateAsync({ add: [], remove: ["C1"] }).catch(() => undefined);
    });

    await waitFor(() =>
      expect(notifyErrorSpy).toHaveBeenCalledWith({
        title: "Could not remove compound. Your list was restored.",
      }),
    );
    expect(qc.getQueryData(key)).toEqual(run);
  });
});
