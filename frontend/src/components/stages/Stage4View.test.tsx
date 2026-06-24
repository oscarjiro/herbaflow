import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisRead } from "../../api/types.gen";
import { Stage4View } from "./Stage4View";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function diseaseTargetsTable(container: HTMLElement) {
  const el = container.querySelector(".table-wrapper");
  if (!el) throw new Error("disease targets table not found");
  return within(el as HTMLElement);
}

const base = {
  analysis_id: "a",
  disease_id: null,
  status: "stage_4_awaiting_approval",
  current_stage: 4,
  parameters: { input_modes: { plant: "selection", disease: "selection" }, disease_targets: {} },
  plants: [],
  diseases: [],
  compounds: [],
} as unknown as AnalysisRead;

describe("Stage4View — single editable table", () => {
  it("uses cleaned heading in the not-applicable state", () => {
    const data = {
      ...base,
      stage_state: { "4": "not_applicable" },
      stage_results: {
        "4": {
          targets: [],
          count: 0,
          min_score_applied: 0.3,
          state: "not_applicable",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(screen.getByRole("heading", { name: "Step 4: Disease Targets" })).toBeInTheDocument();
    expect(screen.getByText(/not applicable/i)).toBeInTheDocument();
  });

  it("uses cleaned empty-result copy", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      parameters: {
        input_modes: { plant: "selection", disease: "selection" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [],
          count: 0,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(
      screen.getByText(
        "No disease targets match this score. Lower the minimum score, run this step again, or add targets manually.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No disease targets —/)).not.toBeInTheDocument();
  });

  it("rounds the score, drops Association, hides removed, shows delete", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "PPARG",
              opentargets_score: 0.123456789,
              association_type: "open_targets_overall",
              tag: "computed",
            },
            {
              target_id: "t2",
              canonical_name: "TP53",
              opentargets_score: 0.5,
              tag: "user-removed",
            },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // Score is display-rounded (formatSig, 4 sig figs).
    expect(screen.getByText("0.1235")).toBeInTheDocument();
    // The near-constant association_type column is gone from the view.
    expect(screen.queryByText("open_targets_overall")).not.toBeInTheDocument();
    // User-removed rows are hidden from the table.
    expect(screen.queryByText("TP53")).not.toBeInTheDocument();
    // The visible row gets an in-table delete control.
    expect(screen.getByRole("button", { name: "Remove PPARG" })).toHaveAttribute(
      "title",
      "Keep at least one target before removing another.",
    );
  });

  it("renders disease-targets with score, min_score card, CSV link and the Open Targets footer", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      parameters: {
        input_modes: { plant: "selection", disease: "selection" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "GENEZ",
              gene_symbol: "GENEZ",
              uniprot_accession: "P55555",
              opentargets_score: 0.8,
              association_type: "overall",
              source_url: "https://www.uniprot.org/uniprotkb/P55555/entry",
              tag: "computed",
            },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(screen.getByText("GENEZ")).toBeInTheDocument();
    expect(screen.getByText("0.8")).toBeInTheDocument();
    // min-score card is shown for a computed run.
    expect(screen.getByText("min score")).toBeInTheDocument();
    // "Open Targets" appears in both the footer and the data-sources block — use getAllByText.
    expect(screen.getAllByText(/Open Targets/i).length).toBeGreaterThan(0);
    // CSV download is rendered as a link.
    const link = screen.getByRole("link", { name: /Download CSV/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("download", "disease-targets.csv");
  });

  it("hides the min-score card, param panel, and user-added tag for a user_provided run", () => {
    const data = {
      ...base,
      stage_state: { "4": "user_provided" },
      parameters: {
        input_modes: { plant: "selection", disease: "manual" },
        disease_targets: { min_score: 0.3 },
      },
      stage_results: {
        "4": {
          targets: [{ target_id: "m1", canonical_name: "MANUALG", tag: "user-added" }],
          count: 1,
          min_score_applied: 0.3,
          state: "user_provided",
        },
      },
    } as unknown as AnalysisRead;

    const { container } = wrap(<Stage4View data={data} />);

    // The manually-added target is shown without a redundant tag badge.
    expect(screen.getByText("MANUALG")).toBeInTheDocument();
    expect(diseaseTargetsTable(container).queryByText("user-added")).not.toBeInTheDocument();
    // The min-score card is gated on !user_provided.
    expect(screen.queryByText("min score")).not.toBeInTheDocument();
    // The disease-target ParamPanel is gated on !user_provided.
    expect(screen.queryByText("Disease-target parameters")).not.toBeInTheDocument();
  });

  it("renders UniProt accession as an ExternalLink to the UniProt entry page", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "PPARG",
              gene_symbol: "PPARG",
              uniprot_accession: "P37231",
              opentargets_score: 0.75,
              source_url: "https://platform.opentargets.org/target/ENSG00000132170",
              tag: "computed",
            },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // UniProt accession is a link to the UniProt entry page (not source_url).
    const link = screen.getByRole("link", { name: /P37231/i });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P37231/entry");
  });

  it("does not render a separate source column for enriched rows", () => {
    const otUrl = "https://platform.opentargets.org/target/ENSG00000132170";
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "PPARG",
              gene_symbol: "PPARG",
              uniprot_accession: "P37231",
              opentargets_score: 0.75,
              source_url: otUrl,
              tag: "computed",
            },
          ],
          count: 1,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    const { container } = wrap(<Stage4View data={data} />);

    const table = diseaseTargetsTable(container);
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    const sourceLinks = table
      .queryAllByRole("link")
      .filter((el) => el.getAttribute("href") === otUrl);
    expect(sourceLinks).toHaveLength(0);
    expect(table.queryByText("Open Targets")).not.toBeInTheDocument();
  });

  it("does not render a separate user-curated source chip for manually-added rows", () => {
    const data = {
      ...base,
      stage_state: { "4": "user_provided" },
      parameters: {
        input_modes: { plant: "selection", disease: "manual" },
        disease_targets: {},
      },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "m1",
              canonical_name: "MANUALTGT",
              gene_symbol: "MANUALTGT",
              uniprot_accession: "Q99999",
              opentargets_score: null,
              source_url: null,
              tag: "user-added",
            },
          ],
          count: 1,
          min_score_applied: 0,
          state: "user_provided",
        },
      },
    } as unknown as AnalysisRead;

    const { container } = wrap(<Stage4View data={data} />);

    const table = diseaseTargetsTable(container);
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(table.queryByText("User-curated")).not.toBeInTheDocument();
    expect(table.queryByText("user-added")).not.toBeInTheDocument();
  });

  it("hides the Open Targets score column when stage_state is user_provided", () => {
    const data = {
      ...base,
      stage_state: { "4": "user_provided" },
      parameters: {
        input_modes: { plant: "selection", disease: "manual" },
        disease_targets: {},
      },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "m1",
              canonical_name: "MANUALTGT",
              gene_symbol: "MANUALTGT",
              uniprot_accession: "Q99999",
              opentargets_score: 0.9,
              source_url: null,
              tag: "user-added",
            },
          ],
          count: 1,
          min_score_applied: 0,
          state: "user_provided",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // The score column header must not appear.
    expect(screen.queryByText("Open Targets score")).not.toBeInTheDocument();
    // The score value itself must not appear either.
    expect(screen.queryByText("0.9")).not.toBeInTheDocument();
  });

  it("delete button reuses the existing remove handler", () => {
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "GENEA",
              gene_symbol: "GENEA",
              uniprot_accession: "P11111",
              opentargets_score: 0.6,
              source_url: null,
              tag: "computed",
            },
            {
              target_id: "t2",
              canonical_name: "GENEB",
              gene_symbol: "GENEB",
              uniprot_accession: "P22222",
              opentargets_score: 0.5,
              source_url: null,
              tag: "computed",
            },
          ],
          count: 2,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    // Both rows have in-table delete buttons via aria-label.
    expect(screen.getByRole("button", { name: "Remove GENEA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove GENEB" })).toBeInTheDocument();
    // Neither is disabled (effectiveCount > 1, so min-entities floor not hit).
    expect(screen.getByRole("button", { name: "Remove GENEA" })).not.toBeDisabled();
  });

  it("passes every target row to DataTable so the shared pager owns pagination", () => {
    const targets = Array.from({ length: 12 }, (_, i) => ({
      target_id: `t${i}`,
      canonical_name: `GENE${i}`,
      gene_symbol: `GENE${i}`,
      uniprot_accession: `P${String(i).padStart(5, "0")}`,
      opentargets_score: 0.9 - i / 100,
      source_url: null,
      tag: "computed",
    }));
    const data = {
      ...base,
      stage_state: { "4": "computed" },
      stage_results: {
        "4": {
          targets,
          count: targets.length,
          min_score_applied: 0.3,
          state: "computed",
        },
      },
    } as unknown as AnalysisRead;

    wrap(<Stage4View data={data} />);

    expect(screen.getByText("Showing 1–10 of 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });
});
