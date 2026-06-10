import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { TargetValidateBox } from "../src/components/TargetValidateBox";
import "../src/lib/api";
import { server } from "./handlers";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const RESOLVED_TARGET = {
  target_id: "t1",
  canonical_key: "uniprot:P04637",
  gene_symbol: "TP53",
  uniprot_accession: "P04637",
  validation_status: "externally_validated",
};

const FAILED_TARGET = {
  value: "NOTAHUMAN",
  reason: "no human UniProt entry found",
  line: 2,
};

test("renders resolved and failed lists, Add button fires onResolved", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({
        resolved: [RESOLVED_TARGET],
        failed: [FAILED_TARGET],
      }),
    ),
  );

  const onResolved = vi.fn();
  render(wrap(<TargetValidateBox onResolved={onResolved} showAddButton />));

  // Type two lines into the textarea
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53\nNOTAHUMAN");

  // Click Validate
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  // Resolved list renders with gene_symbol
  await screen.findByRole("list", { name: "Resolved targets" });
  expect(screen.getByText("TP53")).toBeInTheDocument();

  // Failed list renders with reason
  const failedList = await screen.findByRole("list", { name: "Failed inputs" });
  expect(failedList).toHaveTextContent(/human/i);

  // onResolved not yet called (showAddButton=true)
  expect(onResolved).not.toHaveBeenCalled();

  // Click Add — onResolved fires with the resolved list
  await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

  await waitFor(() => expect(onResolved).toHaveBeenCalledWith([RESOLVED_TARGET]));
});
