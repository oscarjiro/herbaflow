import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { routeTree } from "../../routeTree.gen";
import { Hero } from "./Hero";
import { renderWithRouter } from "../../../tests/renderWithRouter";

afterEach(() => cleanup());

// Mount the full router so TanStack Link renders a real <a> with href.
function makeRouter(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  return { qc, router };
}

function renderLanding() {
  const { qc, router } = makeRouter("/");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

test("Hero renders the full headline", async () => {
  renderLanding();
  expect(await screen.findByText(/End-to-end/i)).toBeInTheDocument();
  // Scope to the hero heading — "network pharmacology" also appears in the footer blurb.
  expect(await screen.findByRole("heading", { name: /network pharmacology/i })).toBeInTheDocument();
});

test("Hero renders the lede paragraph", async () => {
  renderLanding();
  expect(
    await screen.findByText(/Herbaflow runs the full network-pharmacology workflow/i),
  ).toBeInTheDocument();
});

test("Hero CTA links to /analysis", async () => {
  renderLanding();
  const link = await screen.findByRole("link", { name: /start analysis/i });
  expect(link).toBeInTheDocument();
  expect(link).toHaveAttribute("href", "/analysis");
});

describe("Hero", () => {
  it("keeps the intro paragraph on a constrained mobile measure", () => {
    renderWithRouter(<Hero />, { initialEntries: ["/"] });
    const p = screen.getByText(/Herbaflow runs the full network-pharmacology workflow/i);
    // Mobile measure is tighter than the desktop 56ch so it stays within the title block.
    expect(p.className).toMatch(/max-w-\[38ch\]/);
    expect(p.className).toMatch(/sm:max-w-\[56ch\]/);
  });
});
