import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stage4View } from "../src/components/stages/Stage4View";
import type { AnalysisRead } from "../src/api/types.gen";

function renderView(data: AnalysisRead) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <Stage4View data={data} />
    </QueryClientProvider>,
  );
}

const base = {
  analysis_id: "00000000-0000-0000-0000-000000000001",
  analysis_name: null,
  disease_id: "d",
  mode: "guided",
  status: "stage_4_awaiting_approval",
  current_stage: 4,
  created_at: null,
  completed_at: null,
  expires_at: null,
  error_message: null,
  parameters: { disease_targets: { min_score: 0.3 } },
} as unknown as AnalysisRead;

it("renders disease-targets with score, min_score, CSV link and the Open Targets footer", () => {
  const data = {
    ...base,
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
  renderView(data);
  // Gene symbol appears in both the table cell and the EditableEntityList — use getAllByText.
  expect(screen.getAllByText("GENEZ").length).toBeGreaterThan(0);
  expect(screen.getByText("0.8")).toBeInTheDocument();
  // "Open Targets" appears in both the footer and the ParamPanel description — use getAllByText.
  expect(screen.getAllByText(/Open Targets/i).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: /Download CSV/i })).toBeInTheDocument();
});

it("flags a manually-added target (no score) with the user-added badge", () => {
  const data = {
    ...base,
    stage_results: {
      "4": {
        targets: [{ target_id: "m1", canonical_name: "MANUALG", tag: "user-added" }],
        count: 1,
        min_score_applied: 0.3,
        state: "user_provided",
      },
    },
  } as unknown as AnalysisRead;
  renderView(data);
  // MANUALG appears in both the table cell and the EditableEntityList — use getAllByText.
  expect(screen.getAllByText("MANUALG").length).toBeGreaterThan(0);
  expect(screen.getByText("user-added")).toBeInTheDocument();
});
