import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { routeTree } from "../routeTree.gen";

function makeRouter(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  return { qc, router };
}

test("/about renders its heading", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: /about herbaflow/i })).toBeInTheDocument();
});

test("/about renders descriptive content about the platform", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/Indonesian medicinal plants/i)).toBeInTheDocument();
});

test("/ (landing) renders the headline and a link to /analysis", async () => {
  const { qc, router } = makeRouter("/");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: /network pharmacology/i })).toBeInTheDocument();
  // The CTA link to /analysis must be present
  const ctaLink = await screen.findByRole("link", { name: /start analysis/i });
  expect(ctaLink).toBeInTheDocument();
  expect(ctaLink).toHaveAttribute("href", "/analysis");
});

test("/ (landing) nav contains a link to /about", async () => {
  const { qc, router } = makeRouter("/");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  const aboutLink = await screen.findByRole("link", { name: /about/i });
  expect(aboutLink).toBeInTheDocument();
  expect(aboutLink).toHaveAttribute("href", "/about");
});
