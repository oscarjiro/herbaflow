/**
 * Stage8View — Stage 8 functional enrichment (g:Profiler, GO + KEGG). Terminal stage.
 *
 * Param-bearing (`enrichment`: significance_threshold, min_term_size, correction, no_iea,
 * sources). Renders summary
 * cards (input/background gene counts + the shown custom background source), the enriched-terms
 * table + CSV, the param panel (Redo via reset-from/8), honest-null + degraded notices, and the
 * data-sources footer.
 *
 * The stage header, ApprovalBar, and StaleNotice are owned by the StageView shell.
 */

import { useMemo, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  ENRICHMENT_ARRAY_PARAMS,
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
} from "../../contract";
import { enrichmentTermUrl } from "../../lib/externalUrls";
import { humanizeValue } from "../../contract/labels";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { ExpandableListCell } from "@/components/ui/ExpandableListCell";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { EnrichmentDotChart } from "@/components/charts/EnrichmentDotChart";
import { exportPlotlyAsPng } from "@/lib/chartExport";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Local types for the Stage 8 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type Term = {
  source: string;
  term_id: string;
  name: string;
  p_value: number;
  term_size: number;
  query_size: number;
  intersection_size: number;
  intersection: string[];
};

type Stage8Result = {
  state: "computed";
  terms: Term[];
  input_gene_count: number;
  background_gene_count: number;
  background_source: string;
  correction: string;
  significance_threshold: number;
  min_term_size: number;
  sources: string[];
  degraded: boolean;
  count: number;
  flags?: string[];
  stale?: boolean;
};

type EnrichmentParams = Record<string, number | boolean | string | string[]>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export const S8_CSV_HEADER =
  "source,term_id,name,p_value,term_size,intersection_size,intersection,term_url,term_genes";

export function buildS8CsvRows(terms: Term[]): unknown[][] {
  return terms.map((t) => [
    t.source,
    t.term_id,
    t.name,
    t.p_value,
    t.term_size,
    t.intersection_size,
    (t.intersection ?? []).join(" "),
    enrichmentTermUrl(t.source, t.term_id),
    (t.intersection ?? []).join(";"),
  ]);
}

// ---------------------------------------------------------------------------
// Stage8View
// ---------------------------------------------------------------------------

export function Stage8View({ data }: { data: AnalysisRead }) {
  const stage8 = data.stage_results?.["8"] as Stage8Result | undefined;
  const enrichParams = (data.parameters as Record<string, unknown> | undefined)?.enrichment as
    | EnrichmentParams
    | undefined;

  const qc = useQueryClient();
  const redo = useMutation({
    mutationFn: (changed: EnrichmentParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 8 },
        body: { parameters: { "8": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 8");
    },
    onError: (error) => notifyError(error as Problem),
  });

  const gdRef = useRef<HTMLElement | null>(null);

  const terms = useMemo(() => stage8?.terms ?? [], [stage8]);
  const csvRows = useMemo(() => buildS8CsvRows(terms), [terms]);

  if (!stage8) return null;

  // Column definitions — term name links to the term page; genes-in-term uses ExpandableListCell.
  const columns: ColumnDef<Term>[] = [
    {
      id: "source",
      header: "Category",
      cell: ({ row }) => row.original.source,
    },
    {
      id: "term",
      header: "Term",
      cell: ({ row }) => row.original.term_id,
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => {
        const url = enrichmentTermUrl(row.original.source, row.original.term_id);
        return url ? (
          <ExternalLink href={url}>{row.original.name}</ExternalLink>
        ) : (
          row.original.name
        );
      },
    },
    {
      id: "corrected_p",
      header: "Corrected p",
      meta: { className: "num" },
      cell: ({ row }) => formatSig(row.original.p_value),
    },
    {
      id: "term_size",
      header: "Term size",
      meta: { className: "num" },
      cell: ({ row }) => row.original.term_size,
    },
    {
      id: "overlap",
      header: "Overlap",
      meta: { className: "num" },
      cell: ({ row }) => row.original.intersection_size,
    },
    {
      id: "genes",
      header: "Genes in term",
      cell: ({ row }) => (
        <ExpandableListCell items={row.original.intersection ?? []} collapsedCount={0} />
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      <StageDataSources stage={8} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={stage8.count}
          label="enriched terms"
          ariaLabel={`${stage8.count} terms`}
        />
        <StageSummaryCard
          value={stage8.input_gene_count}
          label="query genes"
          ariaLabel={`${stage8.input_gene_count} query genes`}
          muted
        />
        <StageSummaryCard
          value={stage8.background_gene_count}
          label="background genes"
          ariaLabel={`${stage8.background_gene_count} background genes`}
          muted
        />
        <StageSummaryCard
          value={humanizeValue(stage8.correction)}
          label="correction"
          ariaLabel={`correction ${humanizeValue(stage8.correction)}`}
          muted
          // The correction name (e.g. "Benjamini-Hochberg FDR") is a long phrase,
          // not a count — render it smaller so it doesn't dwarf the card.
          valueClassName="text-base leading-tight"
        />
      </div>

      <p className="text-muted-foreground text-sm">
        Background: {stage8.background_source.replace(/_/g, " ")} ({stage8.background_gene_count}{" "}
        genes). Custom universe, not the whole genome.
      </p>

      {stage8.degraded && (
        <div role="status">
          <Badge variant="destructive">
            g:Profiler was unavailable. Enrichment was skipped, but the run still completed.
          </Badge>
        </div>
      )}

      {!stage8.degraded && stage8.count === 0 && (
        <p className="text-muted-foreground text-sm" role="status">
          No terms survived correction at this threshold. The gene set may be small or widely
          distributed.
        </p>
      )}

      {/* Interactive enrichment bubble chart (shown once terms exist) */}
      {terms.length > 0 && (
        <ChartFrame
          title="Pathway enrichment"
          filename="pathway_enrichment.png"
          onExport={async () => {
            if (gdRef.current)
              await exportPlotlyAsPng(gdRef.current, { filename: "pathway_enrichment.png" });
          }}
        >
          <EnrichmentDotChart
            terms={terms.map((t) => ({
              source: t.source,
              name: t.name,
              p_value: t.p_value,
              intersection_size: t.intersection_size,
            }))}
            onGraphDiv={(gd) => (gdRef.current = gd)}
          />
        </ChartFrame>
      )}

      {terms.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <CsvDownloadButton
                header={S8_CSV_HEADER}
                rows={csvRows}
                filename="enrichment.csv"
                label="Download CSV"
              />
            </div>
          </CardHeader>
          <CardContent className="px-0">
            <DataTable columns={columns} data={terms} />
          </CardContent>
        </Card>
      )}

      {/* Enrichment param panel */}
      {enrichParams && (
        <ParamPanel
          params={enrichParams}
          meta={ENRICHMENT_PARAMS}
          numericKeys={ENRICHMENT_NUMERIC_PARAMS}
          booleanKeys={ENRICHMENT_BOOLEAN_PARAMS}
          selectKeys={ENRICHMENT_SELECT_PARAMS}
          arrayKeys={ENRICHMENT_ARRAY_PARAMS}
          title="Enrichment parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      <footer className="text-muted-foreground text-sm">
        <p>
          Enrichment: g:Profiler (GO BP/MF/CC + KEGG), cumulative hypergeometric, custom background
          = the compound-target universe. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
