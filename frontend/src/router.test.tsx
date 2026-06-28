import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { routeTree } from "./routeTree.gen";
import * as useAnalysisStatusModule from "@/hooks/useAnalysisStatus";
import "./lib/api";

// Mock react-cytoscapejs via the shared cytoscape stub (one home).
vi.mock("react-cytoscapejs", () => import("@/test-utils/cytoscapeMock"));

afterEach(() => {
  vi.restoreAllMocks();
});

test("/ renders the landing page with a CTA link to /analysis", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  // The landing page renders the headline and the Start analysis CTA
  expect(await screen.findByRole("heading", { name: /network pharmacology/i })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /start analysis/i })).toBeInTheDocument();
});

test("every page inherits the BackgroundFX dots layer (mounted in the root layout)", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/about"] }),
  });
  const { container } = render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  // The dots layer lives in BackgroundFX; mounting it in __root means a non-landing
  // route (here /about) carries it too — it is no longer landing-only.
  await waitFor(() => {
    expect(container.querySelector("[data-bg-layer='dots']")).toBeTruthy();
  });
});

test("/analysis renders the setup view (New analysis heading)", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/analysis"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("New analysis")).toBeInTheDocument();
});

/**
 * The persistent run shell at /analysis/$id renders a per-stage child route, not
 * the setup view. Deep-linking to a reached pipeline slug mounts that stage's
 * content (here the Stage 1 "compounds" view with the MSW "Alpha" compound).
 *
 * This would have failed under the old flat routing where /analysis/$id rendered
 * the analysis layout's own component (SetupView with its "New analysis" heading).
 */
test("/analysis/$id/<reached stage> renders the run shell, not setup view", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/analysis/r1/compounds"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  // The setup view's "New analysis" heading must never appear in the run shell.
  await waitFor(() => {
    expect(screen.queryByText("New analysis")).not.toBeInTheDocument();
  });

  // After the MSW GET /analyses/r1 poll resolves (status=complete, stage 1 with
  // "Alpha"), the compounds stage view renders the compound name.
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
});

test("/analysis/$id/<unreached> redirects to the furthest reached stage", async () => {
  vi.spyOn(useAnalysisStatusModule, "useAnalysisStatus").mockReturnValue({
    data: {
      analysis_id: "a1",
      status: "stage_3_awaiting_approval",
      current_stage: 3,
      stage_results: { "1": {}, "2": {}, "3": { count: 5 } },
      stage_state: {},
    },
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useAnalysisStatusModule.useAnalysisStatus>);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/analysis/a1/enrichment"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(router.state.location.pathname).toBe("/analysis/a1/targets"));
});

test("/analysis/$id surfaces the service-unavailable screen when the backend is unreachable", async () => {
  // A poll that never reaches the backend rejects with a transport error carrying
  // no HTTP status. The run shell must show ServiceUnavailable (Retry), not poll
  // the status endpoint forever behind an inline "Retrying..." note.
  vi.spyOn(useAnalysisStatusModule, "useAnalysisStatus").mockReturnValue({
    data: undefined,
    isError: true,
    error: new TypeError("Failed to fetch"),
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useAnalysisStatusModule.useAnalysisStatus>);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/analysis/a1/compounds"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: /service unavailable/i })).toBeInTheDocument();
});
