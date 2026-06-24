import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { routeTree } from "../routeTree.gen";

function makeRouter(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  return { qc, router };
}

test("/about renders the masthead heading", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  const h1 = await screen.findByRole("heading", { level: 1, name: /about herbaflow/i });
  expect(h1).toBeInTheDocument();
});

test("/about renders the standfirst deck", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/why this exists, how it works/i)).toBeInTheDocument();
});

test("/about omits the print-style running meta", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { level: 1, name: /about herbaflow/i });
  expect(screen.queryByText(/: about/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/herbaflow · no\. 01/i)).not.toBeInTheDocument();
});

test("/about renders the concept, reason, and approach section headings", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("heading", { level: 2, name: /what network pharmacology is/i }),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: /why this exists/i })).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { level: 2, name: /how herbaflow approaches it/i }),
  ).toBeInTheDocument();
});

test("/about renders the origin-story pull-quote", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByText(/i asked whether there was a better way\. he said no\./i),
  ).toBeInTheDocument();
});

test("/about renders the scope note and the roadmap items", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/research and education tool/i)).toBeInTheDocument();
  expect(screen.getByText(/more sources/i)).toBeInTheDocument();
  expect(screen.getByText(/more plants/i)).toBeInTheDocument();
  expect(screen.getByText(/validation workflows/i)).toBeInTheDocument();
});

test("/about omits the roadmap planned-status label", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { level: 2, name: /what's next/i });
  expect(screen.queryByText(/planned, not yet shipped/i)).not.toBeInTheDocument();
});

test("/about colophon shows contact links with correct hrefs", async () => {
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  const email = await screen.findByRole("link", { name: /oscarjiroj@gmail\.com/i });
  expect(email).toHaveAttribute("href", "mailto:oscarjiroj@gmail.com");
  expect(screen.getByRole("link", { name: /github/i })).toHaveAttribute(
    "href",
    "https://github.com/oscarjiro",
  );
});

test("/about citation is hidden by default and reveals on toggle", async () => {
  const user = userEvent.setup();
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(screen.queryByText(/unpublished thesis project/i)).not.toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: /how to cite/i }));
  expect(await screen.findByText(/unpublished thesis project/i)).toBeInTheDocument();
});

test("/about citation trigger reads as a dropdown button", async () => {
  const user = userEvent.setup();
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  const trigger = await screen.findByRole("button", { name: /how to cite/i });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(trigger.querySelector("svg")).toBeInTheDocument();
  await user.click(trigger);
  expect(trigger).toHaveAttribute("aria-expanded", "true");
});

test("/about renders the Indonesian thesis title in the citation", async () => {
  const user = userEvent.setup();
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await user.click(await screen.findByRole("button", { name: /how to cite/i }));
  expect(
    await screen.findByText(
      /rancang bangun herbaflow platform web network pharmacology dengan studi kasus tumbuhan obat indonesia/i,
    ),
  ).toBeInTheDocument();
});

test("/about copies the provisional citation", async () => {
  const user = userEvent.setup();
  const writeText = vi.spyOn(window.navigator.clipboard, "writeText");
  const { qc, router } = makeRouter("/about");
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await user.click(await screen.findByRole("button", { name: /how to cite/i }));
  await user.click(await screen.findByRole("button", { name: /copy citation/i }));
  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(
      "Jiro, O. (2026). Rancang Bangun Herbaflow Platform Web Network Pharmacology dengan Studi Kasus Tumbuhan Obat Indonesia. Unpublished thesis project.",
    ),
  );
});

test("/about renders the decorative sphere as aria-hidden line-art", async () => {
  const { qc, router } = makeRouter("/about");
  const { container } = render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { level: 1, name: /about herbaflow/i });
  const sphere = container.querySelector(".ab-shape-sphere");
  expect(sphere).toBeInTheDocument();
  expect(sphere).toHaveAttribute("aria-hidden", "true");
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
