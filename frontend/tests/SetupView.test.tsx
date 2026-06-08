import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SetupView } from "../src/components/SetupView";
import "../src/lib/api";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

test("submits a created run id", async () => {
  let createdId: string | null = null;
  render(wrap(<SetupView onCreated={(id) => (createdId = id)} />));

  await screen.findByText("Aaa bbb");
  await userEvent.selectOptions(screen.getByLabelText("Disease"), "d1");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

  await waitFor(() => expect(createdId).toBe("r1"));
});
