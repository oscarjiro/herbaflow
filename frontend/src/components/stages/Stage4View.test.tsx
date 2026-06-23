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
  it("uses cleaned heading in the not-applicable state", () => {
    const data = {
      ...base,
      stage_state: { "4": "not_applicable" },
      stage_results: {
        "4": {
          targets: [],
          count: 0,
          min_score_applied: 0.3,
          state: "not_applicable",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(screen.getByRole("heading", { name: "Step 4: Disease Targets" })).toBeInTheDocument();
    expect(screen.getByText(/not applicable/i)).toBeInTheDocument();
  });

  it("uses cleaned empty-result copy", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      parameters: {
        input_modes: { plant: "selection", disease: "selection" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [],
          count: 0,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(
      screen.getByText(
        "No disease targets match this score. Lower the minimum score, run this step again, or add targets manually.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No disease targets —/)).not.toBeInTheDocument();
  });

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
              opentargets_score: 0.123456789,
              association_type: "open_targets_overall",
              tag: "computed",
            },
            {
              target_id: "t2",
              canonical_name: "TP53",
              opentargets_score: 0.5,
              tag: "user-removed",
            },
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
    expect(screen.getByRole("button", { name: "Remove PPARG" })).toHaveAttribute(
      "title",
      "Keep at least one target before removing another.",
    );
  });

  it("renders disease-targets with score, min_score card, CSV link and the Open Targets footer", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      parameters: {
        input_modes: { plant: "selection", disease: "selection" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "GENEZ",
              gene_symbol: "GENEZ",
              uniprot_accession: "P55555",
              opentargets_score: 0.8,
              association_type: "overall",
              source_url: "https://www.uniprot.org/uniprotkb/P55555/entry",
              tag: "computed",
            },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(screen.getByText("GENEZ")).toBeInTheDocument();
    expect(screen.getByText("0.8")).toBeInTheDocument();
    // min-score card is shown for a computed run.
    expect(screen.getByText("min score")).toBeInTheDocument();
    // "Open Targets" appears in both the footer and the data-sources block — use getAllByText.
    expect(screen.getAllByText(/Open Targets/i).length).toBeGreaterThan(0);
    // CSV download is rendered as a link.
    expect(screen.getByRole("link", { name: /Download CSV/i })).toBeInTheDocument();
  });

  it("hides the min-score card and param panel for a user_provided run", () => {
    const data = {
      ...base,
      stage_state: { "4": "user_provided" },
      parameters: {
        input_modes: { plant: "selection", disease: "manual" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [{ target_id: "m1", canonical_name: "MANUALG", tag: "user-added" }],
          count: 1,
          min_score_applied: 0.3,
          state: "user_provided",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // The manually-added target is shown with the user-added badge.
    expect(screen.getByText("MANUALG")).toBeInTheDocument();
    expect(screen.getByText("user-added")).toBeInTheDocument();
    // The min-score card is gated on !user_provided.
    expect(screen.queryByText("min score")).not.toBeInTheDocument();
    // The disease-target ParamPanel is gated on !user_provided.
    expect(screen.queryByText("Disease-target parameters")).not.toBeInTheDocument();
  });
});
