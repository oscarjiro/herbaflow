import { render, screen } from "@testing-library/react";
import {
  RouterContextProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import type { AnalysisRead } from "@/api/types.gen";
import { StepperRail } from "./StepperRail";

const data: AnalysisRead = {
  analysis_id: "a1",
  status: "stage_3_awaiting_approval",
  current_stage: 3,
  stage_results: { "1": {}, "2": {}, "3": {} },
  stage_state: { "2": "not_applicable" },
} as unknown as AnalysisRead;

function renderTrail(ui: React.ReactNode) {
  const root = createRootRoute({ component: () => null });
  const idx = createRoute({
    getParentRoute: () => root,
    path: "/",
    component: () => null,
  });
  const stage = createRoute({
    getParentRoute: () => root,
    path: "/analysis/$id/$stage",
    component: () => null,
  });
  const router = createRouter({
    routeTree: root.addChildren([idx, stage]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
    defaultPendingMs: 0,
  });
  return render(<RouterContextProvider router={router}>{ui}</RouterContextProvider>);
}

test("renders the eight stages plus the Final bookend, but not Inputs", () => {
  renderTrail(<StepperRail data={data} analysisId="a1" activeSlug="targets" />);
  // Inputs belongs to setup, not the run trail — it must not appear as a step.
  expect(screen.queryByText(/inputs/i)).toBeNull();
  expect(screen.getByText(/final/i)).toBeInTheDocument();
  expect(screen.getByText(/compounds/i)).toBeInTheDocument();
});

test("reached applicable stages are links; locked stages are not", () => {
  renderTrail(<StepperRail data={data} analysisId="a1" activeSlug="targets" />);
  expect(screen.getByRole("link", { name: /targets/i })).toHaveAttribute(
    "href",
    "/analysis/a1/targets",
  );
  expect(screen.queryByRole("link", { name: /enrichment/i })).toBeNull();
});

test("not_applicable stage renders muted and non-navigable", () => {
  renderTrail(<StepperRail data={data} analysisId="a1" activeSlug="targets" />);
  expect(screen.getByText(/not applicable/i)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /adme/i })).toBeNull();
});

test("running stage shows a per-item sub-label from progress", () => {
  const running = {
    ...data,
    status: "stage_3_running",
    progress: { stage: 3, processed: 132, total: 180 },
  } as unknown as AnalysisRead;
  renderTrail(<StepperRail data={running} analysisId="a1" activeSlug="targets" />);
  expect(screen.getByText(/132\s*\/\s*180/)).toBeInTheDocument();
});

test("done steps render a check marker (svg) in icon mode and emit data-state='done'", () => {
  // stage_results has stages 1, 2, 3 reached; compounds (stage 1) is done
  const { container } = renderTrail(
    <StepperRail data={data} analysisId="a1" activeSlug="targets" />,
  );
  const doneMarker = container.querySelector("[data-state='done']");
  expect(doneMarker).not.toBeNull();
  expect(doneMarker!.querySelector("svg")).not.toBeNull();
});
