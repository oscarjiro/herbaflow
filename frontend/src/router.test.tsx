import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { routeTree } from "./routeTree.gen";
import "./lib/api";

// Mock react-cytoscapejs via the shared cytoscape stub (one home).
vi.mock("react-cytoscapejs", () => import("@/test-utils/cytoscapeMock"));

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
  // The landing page renders the app name and the Start an analysis CTA
  expect(await screen.findByRole("heading", { name: /herbaflow/i })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /start an analysis/i })).toBeInTheDocument();
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
 * Regression test for the flat-routing bug where /analysis/$id rendered the
 * analysis layout's own component (SetupView) instead of the $id child route
 * (RunView). The fix splits /analysis into a pure Outlet layout + an index
 * route at /analysis/, so visiting /analysis/$id correctly mounts RunView.
 *
 * This test would have failed before the fix because SetupView (with its "New
 * analysis" heading) would have been rendered instead of RunView.
 */
test("/analysis/$id renders the run view, not setup view", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/analysis/r1"] }),
  });
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  // RunView must mount — it shows a loading skeleton while the first poll is
  // in flight. findByRole with a timeout proves the run view entered the tree.
  // Use a data-testid-free assertion: the skeleton wrapper div appears, OR
  // after the poll resolves a stage label appears. Either way "New analysis"
  // must never appear.
  await waitFor(() => {
    expect(screen.queryByText("New analysis")).not.toBeInTheDocument();
  });

  // After the MSW handler resolves the GET /analyses/r1 poll (status=complete,
  // stage 1 with "Alpha" compound), RunView renders stage content.
  // Wait for something RunView actually renders (the Stage 1 compound name).
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
});
