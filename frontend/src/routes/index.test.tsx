import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter, createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { routeTree } from "../routeTree.gen";

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

test("/ renders every landing section", async () => {
  renderAt("/");
  // Hero
  expect(await screen.findByRole("heading", { name: /network pharmacology/i })).toBeInTheDocument();
  // Stat cards (the compound count is unique; "bioactive compounds" also appears in a timeline step).
  expect(screen.getByText("11,307")).toBeInTheDocument();
  // Workflow timeline
  expect(screen.getByRole("heading", { name: /every one inspectable/i })).toBeInTheDocument();
  // Data-sources strip
  expect(
    screen.getByText(/Every record links back to the database it came from\./i),
  ).toBeInTheDocument();
});

test("/ has exactly one <main> (no nested main)", async () => {
  const { container } = renderAt("/");
  await screen.findByRole("heading", { name: /network pharmacology/i });
  expect(container.querySelectorAll("main")).toHaveLength(1);
});
