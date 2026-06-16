import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisRead } from "../../api/types.gen";
import { StageEntityContext } from "./StageEntityContext";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("StageEntityContext", () => {
  it("shows the manual disease label (no catalog needed)", () => {
    const data = {
      analysis_id: "a",
      disease_id: null,
      parameters: {
        input_modes: { plant: "selection", disease: "manual_disease_targets" },
        labels: { disease: "Type 2 Diabetes" },
      },
      stage_results: {},
    } as unknown as AnalysisRead;
    wrap(<StageEntityContext data={data} side="disease" />);
    // Label and value are in separate child spans; check each part independently.
    expect(screen.getByText(/Disease:/)).toBeInTheDocument();
    expect(screen.getByText("Type 2 Diabetes")).toBeInTheDocument();
  });
});
