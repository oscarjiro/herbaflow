import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";
import { CompoundValidateBox } from "./CompoundValidateBox";
import { server } from "../../tests/handlers";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const RESOLVED_COMPOUND = {
  compound_id: "c1",
  canonical_key: "inchikey:LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
  canonical_name: "ethanol",
  validation_status: "externally_validated",
};

const FAILED_COMPOUND = {
  value: "NOTAKEY",
  reason:
    "not found in the database or PubChem. If it is a real compound, paste its SMILES (structure) instead.",
  line: 2,
};

test("renders resolved and failed lists, Add button fires onResolved", async () => {
  server.use(
    http.post("http://localhost:8000/compounds/validate", () =>
      HttpResponse.json({
        resolved: [RESOLVED_COMPOUND],
        failed: [FAILED_COMPOUND],
      }),
    ),
  );

  const onResolved = vi.fn();
  render(wrap(<CompoundValidateBox onResolved={onResolved} showAddButton />));

  // Type two lines into the editor
  await userEvent.type(screen.getByLabelText("Manual compounds"), "CCO\nNOTAKEY");

  // Click Validate
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  // Resolved list renders with canonical_name
  await screen.findByRole("list", { name: "Resolved compounds" });
  expect(screen.getByText(/ethanol/)).toBeInTheDocument();

  // Failed list is collapsed behind "1 invalid input" control
  const collapseBtn = await screen.findByRole("button", { name: /invalid input/i });
  expect(collapseBtn).toHaveTextContent("1 invalid input");

  // Expand the failed list
  await userEvent.click(collapseBtn);
  const failedList = await screen.findByRole("list", { name: "Failed inputs" });

  // Failed item shows "Line 2:" prefix
  expect(failedList).toHaveTextContent(/Line 2:/);
  expect(failedList).toHaveTextContent(/PubChem/i);

  // onResolved not yet called (showAddButton=true)
  expect(onResolved).not.toHaveBeenCalled();

  // Click Add — onResolved fires with the resolved list
  await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

  await waitFor(() => expect(onResolved).toHaveBeenCalledWith([RESOLVED_COMPOUND]));
});

test("failed item without a line number renders without Line N: prefix", async () => {
  server.use(
    http.post("http://localhost:8000/compounds/validate", () =>
      HttpResponse.json({
        resolved: [],
        failed: [{ value: "BADVAL", reason: "not found anywhere", line: null }],
      }),
    ),
  );

  render(wrap(<CompoundValidateBox onResolved={vi.fn()} />));
  await userEvent.type(screen.getByLabelText("Manual compounds"), "BADVAL");
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  const collapseBtn = await screen.findByRole("button", { name: /invalid input/i });
  await userEvent.click(collapseBtn);

  const failedList = await screen.findByRole("list", { name: "Failed inputs" });
  expect(failedList).not.toHaveTextContent(/Line \d+:/);
  expect(failedList).toHaveTextContent(/not found anywhere/i);
});

test("the line-numbered editor still drives text state", async () => {
  server.use(
    http.post("http://localhost:8000/compounds/validate", () =>
      HttpResponse.json({ resolved: [], failed: [] }),
    ),
  );

  render(wrap(<CompoundValidateBox onResolved={vi.fn()} />));
  const editor = screen.getByRole("textbox", { name: "Manual compounds" });
  await userEvent.type(editor, "CCO");
  expect((editor as HTMLTextAreaElement).value).toBe("CCO");
});
