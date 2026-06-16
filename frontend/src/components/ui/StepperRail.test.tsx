import { render, screen } from "@testing-library/react";
import type { AnalysisRead } from "@/api/types.gen";
import { StepperRail } from "./StepperRail";

const mockRun: AnalysisRead = {
  analysis_id: "test-run-1",
  analysis_name: null,
  disease_id: "disease-1",
  mode: "guided",
  status: "3_awaiting_approval",
  current_stage: 3,
  stage_results: {
    "1": { state: "computed" },
    "2": { state: "computed" },
    "3": { state: "computed" },
  },
  stage_state: {
    "1": "computed",
    "2": "computed",
    "3": "computed",
    "4": "computed",
    "5": "computed",
    "6": "computed",
    "7": "computed",
    "8": "computed",
  },
  parameters: {},
  created_at: null,
  completed_at: null,
  expires_at: null,
  error_message: null,
} as AnalysisRead;

test("renders all 8 stage labels", () => {
  render(<StepperRail data={mockRun} />);
  expect(screen.getByText("Compounds")).toBeInTheDocument();
  expect(screen.getByText("Druglikeness")).toBeInTheDocument();
  expect(screen.getByText("Compound targets")).toBeInTheDocument();
  expect(screen.getByText("Disease targets")).toBeInTheDocument();
  expect(screen.getByText("Shared targets")).toBeInTheDocument();
  expect(screen.getByText("Interaction network")).toBeInTheDocument();
  expect(screen.getByText("Hub genes")).toBeInTheDocument();
  expect(screen.getByText("Pathway enrichment")).toBeInTheDocument();
});

test("marks the current awaiting stage with aria-current=step", () => {
  render(<StepperRail data={mockRun} />);
  // Stage 3 is "3_awaiting_approval" → should be current
  const items = screen.getAllByRole("listitem");
  const stage3 = items[2]; // 0-indexed: stage 3 is index 2
  expect(stage3).toHaveAttribute("aria-current", "step");
});

test("does not mark a later stage as current", () => {
  render(<StepperRail data={mockRun} />);
  const items = screen.getAllByRole("listitem");
  // Hub genes is stage 7 (index 6) — not yet reached
  const hubGenes = items[6];
  expect(hubGenes).not.toHaveAttribute("aria-current", "step");
});

test("marks a not_applicable stage without aria-current", () => {
  const naRun: AnalysisRead = {
    ...mockRun,
    stage_state: {
      ...mockRun.stage_state,
      "2": "not_applicable",
    },
  } as AnalysisRead;
  render(<StepperRail data={naRun} />);
  const items = screen.getAllByRole("listitem");
  const stage2 = items[1];
  expect(stage2).not.toHaveAttribute("aria-current", "step");
});
