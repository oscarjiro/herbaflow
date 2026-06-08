import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { RunView } from "../src/components/RunView";
import "../src/lib/api";

test("renders the stage 1 compound list", async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <RunView analysisId="r1" />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(await screen.findByText(/status: complete/i)).toBeInTheDocument();
});
