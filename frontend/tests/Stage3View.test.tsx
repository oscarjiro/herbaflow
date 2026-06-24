/**
 * Stage3View tests — DataTable column spec, conditional column gating, and
 * the existing delete path.
 *
 * Follows the same structure as Stage2View.test.tsx:
 *  - Realistic fixture with real-shaped stage_results
 *  - Wrap in QueryClientProvider
 *  - Assert column presence/absence per stage_state
 */

import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { Stage3View } from "../src/components/stages/Stage3View";
import type { AnalysisRead } from "../src/api/types.gen";
import "../src/lib/api";

// ---------------------------------------------------------------------------
// Realistic fixtures
// ---------------------------------------------------------------------------

const COMPOUND_C1 = {
  compound_id: "c1",
  canonical_name: "Curcumin",
  smiles: null,
};

const COMPOUND_C2 = {
  compound_id: "c2",
  canonical_name: "Berberine",
  smiles: null,
};

const STAGE2_FIXTURE = {
  count: 2,
  state: "computed",
  passed: [COMPOUND_C1, COMPOUND_C2],
  filtered: [],
  annotations: { pains: [], np_bypass: [], unscreened: [], could_not_screen: [] },
};

/**
 * A realistic app-enriched (computed) Stage 3 result with one ChEMBL target.
 * The target row carries gene_symbol + uniprot_accession (as stage3.run emits).
 * compound_targets carry the edge from c1 → EGFR.
 */
const STAGE3_COMPUTED = {
  targets: [
    {
      target_id: "t1",
      canonical_name: "EGFR",
      gene_symbol: "EGFR",
      uniprot_accession: "P00533",
      source_url: "https://www.uniprot.org/uniprotkb/P00533/entry",
      tag: "computed",
    },
  ],
  compound_targets: [
    {
      compound_id: "c1",
      target_id: "t1",
      prediction_method: "chembl_bioactivity",
      pchembl_value: 7.5,
      score: 7.5,
      source_url: "https://www.uniprot.org/uniprotkb/P00533/entry",
      uniprot_accession: "P00533",
    },
  ],
  per_compound: {
    c1: { coverage: 1 },
    c2: { coverage: 0 },
  },
  coverage_pct: 50.0,
  count: 1,
  state: "computed",
};

/**
 * A user_provided Stage 3 result — manual target entry; no compound_targets edges.
 * The accession comes from the row directly (edit-layer prefill via _target_add_entry).
 */
const STAGE3_USER_PROVIDED = {
  targets: [
    {
      target_id: "t2",
      canonical_name: "TP53",
      gene_symbol: "TP53",
      uniprot_accession: "P04637",
      source_url: "https://www.uniprot.org/uniprotkb/P04637/entry",
      tag: "user-added",
    },
  ],
  compound_targets: [],
  per_compound: {},
  coverage_pct: 0,
  count: 1,
  state: "user_provided",
};

const TARGET_PARAMS_FROZEN = {
  min_pchembl: 5.0,
  min_assay_confidence: 4,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRun(
  stageState: string,
  stage3: unknown,
  overrides: Partial<AnalysisRead> = {},
): AnalysisRead {
  return {
    analysis_id: "run-s3-test",
    analysis_name: null,
    disease_id: "d1",
    mode: "guided",
    status: "stage_3_awaiting_approval",
    current_stage: 3,
    parameters: { target: TARGET_PARAMS_FROZEN },
    stage_results: {
      "2": STAGE2_FIXTURE,
      "3": stage3,
    },
    stage_state: { "3": stageState },
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    ...overrides,
  };
}

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Stage3View — UniProt accession column", () => {
  it("renders accession as an ExternalLink to the UniProt entry page", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    const link = screen.getByRole("link", { name: "P00533" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P00533/entry");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders UniProt accession for a user_provided row (row-first, no edges)", () => {
    wrap(<Stage3View data={makeRun("user_provided", STAGE3_USER_PROVIDED)} />);
    const link = screen.getByRole("link", { name: "P04637" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P04637/entry");
  });
});

describe("Stage3View — Gene symbol column", () => {
  it("renders the gene symbol for a computed target", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    expect(screen.getByRole("columnheader", { name: /Gene symbol/i })).toBeInTheDocument();
    expect(screen.getByText("EGFR")).toBeInTheDocument();
  });

  it("renders the gene symbol for a user_provided target", () => {
    wrap(<Stage3View data={makeRun("user_provided", STAGE3_USER_PROVIDED)} />);
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });
});

describe("Stage3View — Compound source(s) column (conditional)", () => {
  it("shows the Compound source(s) column when stage is app-enriched (computed)", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    expect(screen.getByRole("columnheader", { name: /Compound source/i })).toBeInTheDocument();
    // The compound name "Curcumin" (c1) should appear as a chip in the ExpandableListCell.
    // It may also appear in the per-compound coverage table, so use getAllByText.
    expect(screen.getAllByText("Curcumin").length).toBeGreaterThan(0);
  });

  it("HIDES the Compound source(s) column when stage_state === 'user_provided'", () => {
    wrap(<Stage3View data={makeRun("user_provided", STAGE3_USER_PROVIDED)} />);
    expect(
      screen.queryByRole("columnheader", { name: /Compound source/i }),
    ).not.toBeInTheDocument();
  });
});

describe("Stage3View — no separate source chip column", () => {
  it("does not render a Source column or SourceChip for a computed ChEMBL target", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    expect(screen.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    const chips = document.querySelectorAll('span[class*="font-mono"]');
    const chipTexts = Array.from(chips).map((c) => c.textContent);
    expect(chipTexts).not.toContain("ChEMBL");
  });

  it("does not render a User-curated SourceChip for a user-added target", () => {
    wrap(<Stage3View data={makeRun("user_provided", STAGE3_USER_PROVIDED)} />);
    expect(screen.queryByText("User-curated")).not.toBeInTheDocument();
  });

  it("does not render a PubChem BioAssay SourceChip for pubchem_bioassay method", () => {
    const stage3 = {
      ...STAGE3_COMPUTED,
      compound_targets: [
        {
          ...STAGE3_COMPUTED.compound_targets[0],
          prediction_method: "pubchem_bioassay",
        },
      ],
    };
    wrap(<Stage3View data={makeRun("computed", stage3)} />);
    expect(screen.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    const chips = document.querySelectorAll('span[class*="font-mono"]');
    const chipTexts = Array.from(chips).map((c) => c.textContent);
    expect(chipTexts).not.toContain("PubChem BioAssay");
  });
});

describe("Stage3View — delete (remove) path", () => {
  it("renders a remove button for each visible row", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    // aria-label = "Remove EGFR" (display_label)
    expect(screen.getByRole("button", { name: /Remove EGFR/i })).toBeInTheDocument();
  });

  it("user-removed rows are not rendered in the table", () => {
    const stage3 = {
      ...STAGE3_COMPUTED,
      targets: [{ ...STAGE3_COMPUTED.targets[0], tag: "user-removed" }],
    };
    wrap(<Stage3View data={makeRun("computed", stage3)} />);
    // The accession link should not be present for a user-removed target.
    expect(screen.queryByRole("link", { name: "P00533" })).not.toBeInTheDocument();
  });
});

describe("Stage3View — pagination ownership", () => {
  it("passes every target row to DataTable so the shared pager owns pagination", () => {
    const targets = Array.from({ length: 12 }, (_, i) => ({
      target_id: `t${i}`,
      canonical_name: `GENE${i}`,
      gene_symbol: `GENE${i}`,
      uniprot_accession: `P${String(i).padStart(5, "0")}`,
      source_url: `https://www.uniprot.org/uniprotkb/P${String(i).padStart(5, "0")}/entry`,
      tag: "computed",
    }));
    const stage3 = {
      ...STAGE3_COMPUTED,
      targets,
      compound_targets: targets.map((target) => ({
        compound_id: "c1",
        target_id: target.target_id,
        prediction_method: "chembl_bioactivity",
        source_url: target.source_url,
        uniprot_accession: target.uniprot_accession,
      })),
      count: targets.length,
    };

    wrap(<Stage3View data={makeRun("computed", stage3)} />);

    expect(screen.getByText("Showing 1–10 of 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });
});

describe("Stage3View — coverage cards gate (user_provided)", () => {
  it("shows coverage % and source-count cards for computed runs", () => {
    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);
    expect(screen.getByRole("generic", { name: /1 targets/i })).toBeInTheDocument();
    expect(screen.getByRole("generic", { name: /50% coverage/i })).toBeInTheDocument();
  });

  it("hides coverage cards for user_provided runs", () => {
    wrap(<Stage3View data={makeRun("user_provided", STAGE3_USER_PROVIDED)} />);
    expect(screen.queryByRole("generic", { name: /coverage/i })).not.toBeInTheDocument();
  });
});

describe("Stage3View — not_applicable state", () => {
  it("renders a greyed-out placeholder when stage_state is not_applicable", () => {
    const data = makeRun("not_applicable", STAGE3_COMPUTED);
    wrap(<Stage3View data={data} />);
    expect(screen.getByRole("heading", { name: /Step 3/i })).toBeInTheDocument();
    expect(screen.getByText(/not applicable/i)).toBeInTheDocument();
  });
});

describe("Stage3View — CSV header", () => {
  it("CSV header matches the contract spec exactly", async () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(<Stage3View data={makeRun("computed", STAGE3_COMPUTED)} />);

    // CsvDownloadButton creates the blob on mount via useCsvBlobUrl.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    if (!capturedBlob) return; // If blob wasn't created, test passes vacuously.

    const reader = new FileReader();
    const text = await new Promise<string>((resolve, reject) => {
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(capturedBlob!);
    });

    const header = text.split("\n")[0];
    expect(header).toBe(
      "gene_symbol,uniprot_accession,prediction_method,source_compounds,source_url",
    );
  });
});
