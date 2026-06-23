import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "@/lib/theme";
import { Stage5View } from "./Stage5View";
import type { AnalysisRead } from "../../api/types.gen";

function makeStage5Result(overrides?: { overlap?: object[] }) {
  return {
    overlap: overrides?.overlap ?? [
      {
        target_id: "T1",
        gene_symbol: "EGFR",
        uniprot_accession: "P00533",
        opentargets_score: 0.85,
      },
      {
        target_id: "T2",
        gene_symbol: "TP53",
        uniprot_accession: "P04637",
        opentargets_score: 0.72,
      },
    ],
    count: 2,
    compound_target_count: 40,
    disease_target_count: 30,
    unmapped_count: 0,
    state: "computed",
    flags: [],
  };
}

function makeData(overrides?: { overlap?: object[] }): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "stage_5_awaiting_approval",
    current_stage: 5,
    parameters: {},
    stage_results: { "5": makeStage5Result(overrides) },
    stage_state: {},
    plants: [],
    diseases: [],
    compounds: [],
  } as unknown as AnalysisRead;
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </ThemeProvider>,
  );
}

describe("Stage5View — overlap view", () => {
  it("renders the overlap count card", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByLabelText(/2 overlap targets/i)).toBeInTheDocument();
  });

  it("renders both gene-symbol rows", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
  });

  it("does NOT render Jaccard, p-value, or a significance badge", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.queryByText(/jaccard/i)).toBeNull();
    expect(screen.queryByText(/p-value/i)).toBeNull();
    expect(screen.queryByText(/significant/i)).toBeNull();
  });

  it("does not render a param panel or Redo button", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.queryByRole("button", { name: /redo/i })).toBeNull();
    expect(screen.queryByText(/parameters/i)).toBeNull();
  });

  it("renders the interactive venn chart inside a ChartFrame when complete and counts > 0", () => {
    const completeData: AnalysisRead = {
      ...makeData(),
      status: "complete",
    } as unknown as AnalysisRead;
    wrap(<Stage5View data={completeData} />);
    // ChartFrame renders the title in its card header and shows a Download PNG button
    // (getAllByText because the SVG <title> also contains the same string)
    const titleNodes = screen.getAllByText("Target overlap");
    expect(titleNodes.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
    // The old server-rendered PNG img is gone
    expect(screen.queryByRole("img", { name: /target overlap/i })).toBeNull();
  });

  it("renders the venn once the step has results, even before the run completes", () => {
    // counts > 0 on an awaiting-approval (not yet complete) run — the chart shows.
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getAllByText("Target overlap").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("does not render the venn when both set sizes are zero", () => {
    const data = makeData({ overlap: [] });
    data.stage_results = {
      "5": {
        ...makeStage5Result({ overlap: [] }),
        count: 0,
        compound_target_count: 0,
        disease_target_count: 0,
      },
    } as unknown as AnalysisRead["stage_results"];
    wrap(<Stage5View data={data} />);
    expect(screen.queryByText("Target overlap")).toBeNull();
    expect(screen.queryByRole("button", { name: /download png/i })).toBeNull();
  });

  it("does NOT render a StaleNotice even when the stage is stale (notice belongs under the edited stage, never here)", () => {
    // Stage 3 was edited (rerun_from === 3); Stage 5 is downstream-stale.
    // The StaleNotice must appear under Stage 3, not Stage 5.
    const data = makeData();
    data.parameters = { rerun_from: 3 } as AnalysisRead["parameters"];
    data.stage_results = {
      "5": {
        ...makeStage5Result(),
        stale: true,
      },
    } as unknown as AnalysisRead["stage_results"];

    wrap(<Stage5View data={data} />);

    expect(
      screen.queryByText("These results are out of date. An earlier step changed."),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-run from step/i })).not.toBeInTheDocument();
  });
});
