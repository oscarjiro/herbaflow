import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { StpDialog } from "../src/components/stages/StpDialog";
import "../src/lib/api";
import { server } from "./handlers";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

// Real SwissTargetPrediction export shape: quoted header, "Probability*" column.
const CSV = `"Target","Common name","Uniprot ID","ChEMBL ID","Target Class","Probability*","Known actives (3D/2D)"
"Cellular tumor antigen p53","TP53","P04637","CHEMBL4096","TF","0.90","5"
"Epidermal growth factor receptor","EGFR","P00533","CHEMBL203","Kinase","0.80","3"`;

const COMPOUNDS = [{ compound_id: "c1", canonical_name: "beta-Curcumene", smiles: "CCO" }];

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

  fireEvent.change(screen.getByLabelText("Paste SwissTargetPrediction CSV"), {
    target: { value: CSV },
  });
  // Both rows are at/above the default 0.6 threshold.
  expect(screen.getByText(/2 rows at or above threshold/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Import" }));

  // Resolution goes through the manual-add path (/targets/validate), not an STP endpoint.
  await waitFor(() => expect(validate).toHaveBeenCalledTimes(1));

  // Only the fresh target (t1) is added to the run; t2 is already present.
  await waitFor(() => expect(onAddTargets).toHaveBeenCalledTimes(1));
  expect(onAddTargets).toHaveBeenCalledWith([expect.objectContaining({ target_id: "t1" })]);

  // Counters reflect added / already-in-run / failed.
  await screen.findByText(/Added 1 target\(s\) to the run; 1 already present; 0 failed to resolve\./);
});
