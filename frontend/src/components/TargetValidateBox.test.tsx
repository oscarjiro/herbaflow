import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LazyMotion, domAnimation } from "motion/react";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";
import { TargetValidateBox } from "./TargetValidateBox";
import { server } from "../../tests/handlers";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <LazyMotion features={domAnimation}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </LazyMotion>
  );
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

function makeResolvedTargets(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    target_id: `t${index}`,
    canonical_key: `uniprot:P${String(index).padStart(5, "0")}`,
    gene_symbol: `GENE${index}`,
    uniprot_accession: `P${String(index).padStart(5, "0")}`,
    validation_status: "externally_validated",
  }));
}

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

  // Type two lines into the editor
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53\nNOTAHUMAN");

  // Click Validate
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  // Resolved list renders with gene_symbol
  await screen.findByRole("list", { name: "Resolved targets" });
  expect(screen.getByText("TP53")).toBeInTheDocument();

  // Failed list is collapsed behind "1 invalid input" control
  const collapseBtn = await screen.findByRole("button", { name: /invalid input/i });
  expect(collapseBtn).toHaveTextContent("1 invalid input");

  // Expand the failed list
  await userEvent.click(collapseBtn);
  const failedList = await screen.findByRole("list", { name: "Failed inputs" });

  // Failed item shows "Line 2:" prefix
  expect(failedList).toHaveTextContent(/Line 2:/);
  expect(failedList).toHaveTextContent(/human/i);

  // onResolved not yet called (showAddButton=true)
  expect(onResolved).not.toHaveBeenCalled();

  // Click Add — onResolved fires with the resolved list
  await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

  await waitFor(() => expect(onResolved).toHaveBeenCalledWith([RESOLVED_TARGET]));
});

test("failed item without a line number renders without Line N: prefix", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({
        resolved: [],
        failed: [{ value: "BADVAL", reason: "not recognised", line: null }],
      }),
    ),
  );

  render(wrap(<TargetValidateBox onResolved={vi.fn()} />));
  await userEvent.type(screen.getByLabelText("Add targets"), "BADVAL");
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  const collapseBtn = await screen.findByRole("button", { name: /invalid input/i });
  await userEvent.click(collapseBtn);

  const failedList = await screen.findByRole("list", { name: "Failed inputs" });
  expect(failedList).not.toHaveTextContent(/Line \d+:/);
  expect(failedList).toHaveTextContent(/not recognised/i);
});

test("collapses large resolved-target batches behind the shared overflow dialog", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({
        resolved: makeResolvedTargets(12),
        failed: [],
      }),
    ),
  );

  render(wrap(<TargetValidateBox onResolved={vi.fn()} showAddButton />));
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53");
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  await screen.findByRole("list", { name: "Resolved targets" });
  expect(screen.getByText("GENE0")).toBeInTheDocument();
  expect(screen.queryByText("GENE10")).not.toBeInTheDocument();

  const overflow = screen.getByRole("button", { name: /show all 12 items/i });
  expect(overflow).toHaveTextContent("+2 more");

  await userEvent.click(overflow);
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(screen.getByText(/of 12/i)).toBeInTheDocument();
});

test("shows the shared busy button and progress bar while targets validate", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () => new Promise(() => undefined)),
  );

  render(wrap(<TargetValidateBox onResolved={vi.fn()} showAddButton />));
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53\nEGFR\nAKT1");
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  const button = await screen.findByRole("button", { name: /working/i });
  expect(button).toHaveAttribute("aria-busy", "true");
  expect(button).toHaveAttribute("data-variant", "secondary");
  expect(button).toHaveClass("w-full");
  expect(button.parentElement).toHaveClass("w-full");
  expect(screen.getByText(/Validating 0 of 3 target entries/)).toBeInTheDocument();
  const bar = screen.getByRole("progressbar");
  expect(bar).toHaveAttribute("aria-valuemax", "3");
});

test("requires adding the validated target batch before validating again", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({
        resolved: [RESOLVED_TARGET],
        failed: [],
      }),
    ),
  );

  render(wrap(<TargetValidateBox onResolved={vi.fn()} showAddButton />));
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53");
  await userEvent.click(screen.getByRole("button", { name: /validate/i }));

  await screen.findByRole("button", { name: /^add$/i });
  const validateButton = screen.getByRole("button", { name: /validate/i });
  expect(validateButton).toBeDisabled();

  // Add clears the editor; an empty box keeps Validate disabled until new input.
  await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
  expect(validateButton).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Add targets"), "EGFR");
  expect(validateButton).not.toBeDisabled();
});

test("disables Validate until the editor has non-whitespace input", async () => {
  render(wrap(<TargetValidateBox onResolved={vi.fn()} />));
  const validateButton = screen.getByRole("button", { name: /validate/i });

  // Empty box: nothing to validate.
  expect(validateButton).toBeDisabled();

  // Whitespace-only is still empty.
  await userEvent.type(screen.getByLabelText("Add targets"), "   ");
  expect(validateButton).toBeDisabled();

  // Real content enables it.
  await userEvent.type(screen.getByLabelText("Add targets"), "TP53");
  expect(validateButton).not.toBeDisabled();
});

test("the line-numbered editor still drives text state", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({ resolved: [], failed: [] }),
    ),
  );

  render(wrap(<TargetValidateBox onResolved={vi.fn()} />));
  const editor = screen.getByRole("textbox", { name: "Add targets" });
  await userEvent.type(editor, "ABC");
  // The editor is a real textarea so its value should update
  expect((editor as HTMLTextAreaElement).value).toBe("ABC");
});
