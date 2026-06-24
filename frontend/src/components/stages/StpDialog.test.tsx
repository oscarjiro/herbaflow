import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, test, vi } from "vitest";
import { StpDialog } from "./StpDialog";
import * as sdkModule from "../../api/sdk.gen";
import * as toastLib from "../../lib/toast";
import { server } from "../../../tests/handlers";

// Real SwissTargetPrediction export shape: quoted header, "Probability*" column.
const CSV = `"Target","Common name","Uniprot ID","ChEMBL ID","Target Class","Probability*","Known actives (3D/2D)"
"Cellular tumor antigen p53","TP53","P04637","CHEMBL4096","TF","0.90","5"
"Epidermal growth factor receptor","EGFR","P00533","CHEMBL203","Kinase","0.80","3"`;

const COMPOUNDS = [
  {
    compound_id: "c1",
    canonical_name: "beta-Curcumene",
    smiles: "CCO",
  },
];

const COMPOUNDS_MULTI = [
  {
    compound_id: "C1",
    canonical_name: "Quercetin",
    smiles: "OC1=CC=CC=C1",
    source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/5280343",
  },
  {
    compound_id: "C2",
    canonical_name: "Curcumin",
    smiles: null,
    source_url: null,
  },
];

const PER_COMPOUND_MULTI = {
  C1: { coverage: 0 },
  C2: { coverage: 0.5 },
};

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Open the STP dialog by clicking its trigger button. */
async function openDialog() {
  await userEvent.click(screen.getByRole("button", { name: /add swisstargetprediction targets/i }));
}

test("uses cleaned SwissTargetPrediction import copy", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  expect(
    screen.getByRole("heading", { name: "Add targets from SwissTargetPrediction" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Select one compound with few target matches, copy its SMILES into SwissTargetPrediction, then paste the CSV here. New targets are added only to this analysis.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByText(/manual paste-back/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/measured compound/i)).not.toBeInTheDocument();
});

test("uses a single compound selection and copies only that compound's SMILES", async () => {
  vi.stubGlobal("navigator", {
    ...navigator,
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });

  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();
  expect(screen.queryByRole("checkbox", { name: /select quercetin/i })).not.toBeInTheDocument();

  const quercetin = screen.getByRole("radio", { name: /select quercetin/i });
  const curcumin = screen.getByRole("radio", { name: /select curcumin/i });

  await userEvent.click(quercetin);
  expect(quercetin).toBeChecked();
  expect(curcumin).not.toBeChecked();

  await userEvent.click(curcumin);
  expect(quercetin).not.toBeChecked();
  expect(curcumin).toBeChecked();

  await userEvent.click(quercetin);
  await userEvent.click(screen.getByRole("button", { name: /copy smiles/i }));

  expect(navigator.clipboard.writeText).toHaveBeenCalledWith("OC1=CC=CC=C1");
  expect(await screen.findByText("Copied SMILES for Quercetin.")).toBeInTheDocument();
  expect(screen.queryByText(/skipped — no SMILES/)).not.toBeInTheDocument();
});

test("uses clickable compound rows and icon-only SMILES status", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  const quercetin = screen.getByRole("radio", { name: /select quercetin/i });
  const row = quercetin.closest("tr");
  const radioCell = quercetin.closest("td");

  expect(row).toHaveClass("cursor-pointer");
  expect(radioCell).toHaveClass("text-center");
  expect(quercetin).toHaveClass("cursor-pointer");
  expect(
    screen.getByLabelText("SMILES available for Quercetin").querySelector("svg"),
  ).not.toBeNull();
  expect(screen.getByLabelText("SMILES missing for Curcumin").querySelector("svg")).not.toBeNull();
  expect(screen.queryByText("Ready")).not.toBeInTheDocument();
  expect(screen.queryByText("Missing")).not.toBeInTheDocument();
});

test("links STP compounds to their source URL when available", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  const sourceLink = screen.getByRole("link", { name: "Open source for Quercetin" });
  expect(sourceLink).toHaveAttribute("href", "https://pubchem.ncbi.nlm.nih.gov/compound/5280343");
  expect(sourceLink.querySelector("svg")).not.toBeNull();
  expect(screen.queryByRole("link", { name: "Open source for Curcumin" })).not.toBeInTheDocument();
});

test("filters the least-covered compound list by name", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  expect(screen.getByText("Quercetin")).toBeInTheDocument();
  expect(screen.getByText("Curcumin")).toBeInTheDocument();

  const search = screen.getByRole("searchbox", { name: /search compounds/i });
  expect(search).toHaveAttribute("placeholder", "Search by name");

  await userEvent.type(search, "quer");

  expect(screen.getByText("Quercetin")).toBeInTheDocument();
  expect(screen.queryByText("Curcumin")).not.toBeInTheDocument();
});

test("does not show or search by InChIKey in the compound picker", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  expect(screen.queryByRole("columnheader", { name: "InChIKey" })).not.toBeInTheDocument();

  await userEvent.type(
    screen.getByRole("searchbox", { name: /search compounds/i }),
    "VFLDPWHFBUODDF",
  );

  expect(screen.queryByText("Curcumin")).not.toBeInTheDocument();
  expect(screen.queryByText("Quercetin")).not.toBeInTheDocument();
  expect(screen.getByText("No compounds match this search.")).toBeInTheDocument();
});

test("keeps dialog overflow hidden and gives the compound table the only vertical scroller", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  const dialog = screen.getByRole("dialog", { name: /add targets from swisstargetprediction/i });
  const compoundGroup = screen.getByRole("group", { name: /compounds to screen/i });
  const compoundsRegion = screen.getByRole("region", { name: /selectable compounds/i });
  const pasteBox = screen.getByLabelText("Paste SwissTargetPrediction CSV");
  const body = compoundGroup.parentElement;

  expect(dialog.className).toContain("sm:max-w-5xl");
  expect(dialog).toHaveClass("overflow-hidden");
  expect(dialog).not.toHaveClass("overflow-y-auto");
  expect(body).not.toHaveClass("grid");
  expect(body).toHaveClass("flex");
  expect(compoundsRegion).toHaveClass("scroll");
  expect(compoundsRegion).toHaveClass("overflow-x-hidden");
  expect(compoundsRegion.className).toMatch(/max-h-/);
  expect(pasteBox).toHaveClass("h-32");
  expect(pasteBox).toHaveClass("overflow-y-auto");
  expect(pasteBox).toHaveClass("resize-none");
});

test("renders icon-backed STP utility actions with command labels", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS_MULTI}
        perCompound={PER_COMPOUND_MULTI}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();

  const copyButton = screen.getByRole("button", { name: /copy smiles/i });
  const openLink = screen.getByRole("link", { name: /open swisstargetprediction/i });

  expect(copyButton.querySelector("svg")).not.toBeNull();
  expect(openLink.querySelector("svg")).not.toBeNull();
  expect(openLink).not.toHaveClass("hf-glass");
});

test("uses cleaned import result summary", async () => {
  server.use(
    http.post("http://localhost:8000/targets/validate", () =>
      HttpResponse.json({
        resolved: [
          {
            target_id: "t1",
            canonical_key: "uniprot:P04637",
            gene_symbol: "TP53",
            uniprot_accession: "P04637",
            validation_status: "externally_validated",
          },
          {
            target_id: "t2",
            canonical_key: "uniprot:P00533",
            gene_symbol: "EGFR",
            uniprot_accession: "P00533",
            validation_status: "db_hit",
          },
        ],
        failed: [{ input: "BAD", reason: "not found" }],
      }),
    ),
  );

  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS}
        perCompound={{ c1: { coverage: 0 } }}
        existingTargetIds={["t2"]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();
  fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
    target: { value: CSV },
  });
  await userEvent.click(screen.getByRole("button", { name: "Import" }));

  expect(
    await screen.findByText("Added 1 target. 1 was already present. 1 could not be matched."),
  ).toBeInTheDocument();
});

test("summarizes parsed STP targets without rendering a preview table", async () => {
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS}
        perCompound={{ c1: { coverage: 0 } }}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();
  fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
    target: { value: CSV },
  });

  expect(
    screen.getByText("2 protein targets read from CSV at or above threshold."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "UniProt" })).not.toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "Common name" })).not.toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "Probability" })).not.toBeInTheDocument();
});

test("import resolves via /targets/validate and adds only fresh targets to the run", async () => {
  const validate = vi.fn();
  server.use(
    http.post("http://localhost:8000/targets/validate", async ({ request }) => {
      validate(await request.json());
      return HttpResponse.json({
        resolved: [
          {
            target_id: "t1",
            canonical_key: "uniprot:P04637",
            gene_symbol: "TP53",
            uniprot_accession: "P04637",
            validation_status: "externally_validated",
          },
          {
            target_id: "t2",
            canonical_key: "uniprot:P00533",
            gene_symbol: "EGFR",
            uniprot_accession: "P00533",
            validation_status: "db_hit",
          },
        ],
        failed: [],
      });
    }),
  );

  const onAddTargets = vi.fn();
  // t2 (EGFR) is already in the run; only t1 (TP53) is fresh.
  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS}
        perCompound={{ c1: { coverage: 0 } }}
        existingTargetIds={["t2"]}
        onAddTargets={onAddTargets}
      />,
    ),
  );

  // Open the dialog first.
  await openDialog();

  fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
    target: { value: CSV },
  });
  // Both rows are at/above the default 0.6 threshold.
  expect(
    screen.getByText("2 protein targets read from CSV at or above threshold."),
  ).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Import" }));

  // Resolution goes through the manual-add path (/targets/validate), not an STP endpoint.
  await waitFor(() => expect(validate).toHaveBeenCalledTimes(1));

  // Only the fresh target (t1) is added to the run; t2 is already present.
  await waitFor(() => expect(onAddTargets).toHaveBeenCalledTimes(1));
  expect(onAddTargets).toHaveBeenCalledWith([expect.objectContaining({ target_id: "t1" })]);

  // Counters reflect added / already-in-run / failed.
  await screen.findByText("Added 1 target. 1 was already present. 0 could not be matched.");
});

test("uses the shared stateful button for STP import progress", async () => {
  let resolveRequest!: () => void;
  const requestStarted = vi.fn();
  const pendingRequest = new Promise<void>((resolve) => {
    resolveRequest = resolve;
  });
  server.use(
    http.post("http://localhost:8000/targets/validate", async () => {
      requestStarted();
      await pendingRequest;
      return HttpResponse.json({ resolved: [], failed: [] });
    }),
  );

  render(
    wrap(
      <StpDialog
        compounds={COMPOUNDS}
        perCompound={{ c1: { coverage: 0 } }}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    ),
  );

  await openDialog();
  fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
    target: { value: CSV },
  });

  const importButton = screen.getByRole("button", { name: "Import" });
  expect(importButton).toHaveAttribute("data-variant", "default");
  expect(importButton).not.toHaveClass("hf-glass");

  fireEvent.click(importButton);

  await waitFor(() => expect(requestStarted).toHaveBeenCalledTimes(1));
  const workingButton = await screen.findByRole("button", { name: /working/i });
  expect(workingButton).toHaveAttribute("aria-busy", "true");
  expect(workingButton).toHaveAttribute("data-variant", "default");
  expect(workingButton).not.toHaveClass("hf-glass");
  resolveRequest();
  expect(await screen.findByText("Done")).toBeInTheDocument();
});

describe("StpDialog — D10: disabled Import reason hint", () => {
  it("shows a 'paste a valid CSV to import' hint when no rows are parsed (import disabled)", async () => {
    render(
      wrap(
        <StpDialog
          compounds={COMPOUNDS_MULTI}
          perCompound={PER_COMPOUND_MULTI}
          existingTargetIds={[]}
          onAddTargets={() => {}}
        />,
      ),
    );

    // Open the dialog first.
    await openDialog();

    // Import button should be disabled
    const importBtn = screen.getByRole("button", { name: /^import$/i });
    expect(importBtn).toBeDisabled();

    // A reason hint must be present when import is disabled
    expect(screen.getByText(/paste a valid csv to import/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// D-4: Toast wiring for StpDialog import
// ---------------------------------------------------------------------------

describe("StpDialog — D-4 toast wiring", () => {
  afterEach(() => vi.restoreAllMocks());

  it("fires notifySuccess with the added count on import success", async () => {
    server.use(
      http.post("http://localhost:8000/targets/validate", () =>
        HttpResponse.json({
          resolved: [
            {
              target_id: "t1",
              canonical_key: "uniprot:P04637",
              gene_symbol: "TP53",
              uniprot_accession: "P04637",
              validation_status: "externally_validated",
            },
          ],
          failed: [],
        }),
      ),
    );

    const notifySuccessSpy = vi.spyOn(toastLib, "notifySuccess").mockImplementation(() => {});

    render(
      wrap(
        <StpDialog
          compounds={COMPOUNDS}
          perCompound={{ c1: { coverage: 0 } }}
          existingTargetIds={[]}
          onAddTargets={() => {}}
        />,
      ),
    );

    await openDialog();
    fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
      target: { value: CSV },
    });
    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(notifySuccessSpy).toHaveBeenCalledWith("Imported 1 targets"));
  });

  it("fires notifyError (not ad-hoc toast) when import fails", async () => {
    // Reject the SDK call directly so TanStack Query routes it to onError.
    vi.spyOn(sdkModule, "validateTargets").mockRejectedValue({ detail: "Service error." });
    const notifyErrorSpy = vi.spyOn(toastLib, "notifyError").mockImplementation(() => {});

    render(
      wrap(
        <StpDialog
          compounds={COMPOUNDS}
          perCompound={{ c1: { coverage: 0 } }}
          existingTargetIds={[]}
          onAddTargets={() => {}}
        />,
      ),
    );

    await openDialog();
    fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
      target: { value: CSV },
    });
    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(notifyErrorSpy).toHaveBeenCalledTimes(1));
  });
});
