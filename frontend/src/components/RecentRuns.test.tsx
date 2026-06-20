import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createRouter,
  createMemoryHistory,
  createRootRoute,
  createRoute,
} from "@tanstack/react-router";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { server, SAMPLE_ANALYSES_LIST } from "../../tests/handlers";
import { RecentRuns } from "./RecentRuns";

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wraps RecentRuns in a minimal TanStack Router context so <Link to="/analysis/$id">
 * resolves without throwing. We build a tiny two-route tree: / renders RecentRuns,
 * /analysis/$id is a stub. This avoids pulling in the full SetupView route tree.
 */
function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  const rootRoute = createRootRoute({ component: () => <>{ui}</> });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => null,
  });
  const analysisIdRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/analysis/$id",
    component: () => null,
  });

  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute, analysisIdRoute]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });

  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests — rows and labels
// ---------------------------------------------------------------------------

describe("RecentRuns — rows and labels", () => {
  it("renders a row for each run returned from GET /analyses", async () => {
    wrap(<RecentRuns />);
    // r1 has a name
    await screen.findByText("My first run");
    // r2 has no name — should fall back to analysis_id
    await screen.findByText("r2");
  });

  it("shows plant name from catalog for selection mode", async () => {
    wrap(<RecentRuns />);
    // r1: plant mode selection, plant_ids: ["p1"] → "Aaa bbb" from GET /plants
    await screen.findByText(/Aaa bbb/);
  });

  it("shows disease name from catalog for selection mode", async () => {
    wrap(<RecentRuns />);
    // r1: disease mode selection, disease_id: "d1" → "Test Disease" from GET /diseases.
    // Both rows use d1 so we expect at least one matching element.
    const matches = await screen.findAllByText(/Test Disease/);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("shows manual plant label for manual_compounds mode", async () => {
    wrap(<RecentRuns />);
    // r2: plant mode manual_compounds, labels.plant = "My herb"
    await screen.findByText(/My herb/);
  });

  it("shows formatted status badge for complete run", async () => {
    wrap(<RecentRuns />);
    await screen.findByText("Complete");
  });

  it("shows formatted status badge for awaiting-approval run", async () => {
    wrap(<RecentRuns />);
    await screen.findByText("Waiting for review");
  });

  it("shows the created_at date formatted with toLocaleDateString", async () => {
    wrap(<RecentRuns />);
    await waitFor(() => {
      const dateText = new Date(SAMPLE_ANALYSES_LIST[0]!.created_at!).toLocaleDateString();
      expect(screen.getByText(dateText)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Tests — empty state
// ---------------------------------------------------------------------------

describe("RecentRuns — empty state", () => {
  it("shows 'No runs yet.' when the list is empty", async () => {
    server.use(http.get("http://localhost:8000/analyses", () => HttpResponse.json([])));
    wrap(<RecentRuns />);
    await screen.findByText("No runs yet.");
  });
});

// ---------------------------------------------------------------------------
// Tests — loading state
// ---------------------------------------------------------------------------

describe("RecentRuns — loading state", () => {
  it("renders skeleton rows while loading", async () => {
    // Delay the /analyses response so we catch the loading state
    server.use(
      http.get("http://localhost:8000/analyses", async () => {
        await new Promise<void>((resolve) => setTimeout(resolve, 5000));
        return HttpResponse.json([]);
      }),
    );
    wrap(<RecentRuns />);
    // The loading container should appear while the delayed response is in flight
    await screen.findByLabelText("Loading recent runs");
  });
});

// ---------------------------------------------------------------------------
// Tests — resume links
// ---------------------------------------------------------------------------

describe("RecentRuns — resume links", () => {
  it("each run row is a link pointing to /analysis/<id>", async () => {
    wrap(<RecentRuns />);
    // Wait for rows to appear
    await screen.findByText("My first run");
    const list = screen.getByRole("list", { name: /recent runs/i });
    const links = list.querySelectorAll("a");
    expect(links).toHaveLength(2);
    const hrefs = Array.from(links).map((a) => a.getAttribute("href"));
    expect(hrefs.some((h) => h?.includes("r1"))).toBe(true);
    expect(hrefs.some((h) => h?.includes("r2"))).toBe(true);
  });
});
