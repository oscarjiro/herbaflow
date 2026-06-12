import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisRead } from "../../api/types.gen";
import { Stage4View } from "./Stage4View";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const base = {
  analysis_id: "a",
  disease_id: null,
  status: "stage_4_awaiting_approval",
  current_stage: 4,
  parameters: { input_modes: { plant: "selection", disease: "selection" }, disease_targets: {} },
  plants: [],
  diseases: [],
  compounds: [],
} as unknown as AnalysisRead;

describe("Stage4View — single editable table", () => {
  it("rounds the score, drops Association, hides removed, shows delete", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "PPARG",
              score: 0.123456789,
              association_type: "open_targets_overall",
              tag: "computed",
            },
            { target_id: "t2", canonical_name: "TP53", score: 0.5, tag: "user-removed" },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // Score is display-rounded (formatSig, 4 sig figs).
    expect(screen.getByText("0.1235")).toBeInTheDocument();
    // The near-constant association_type column is gone from the view.
    expect(screen.queryByText("open_targets_overall")).not.toBeInTheDocument();
    // User-removed rows are hidden from the table.
    expect(screen.queryByText("TP53")).not.toBeInTheDocument();
    // The visible row gets an in-table delete control.
    expect(screen.getByRole("button", { name: "Remove PPARG" })).toBeInTheDocument();
  });
});
