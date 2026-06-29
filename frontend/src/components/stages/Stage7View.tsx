/**
 * Stage7View — Stage 7 hub-gene ranking (networkx centralities + Maximal Clique Centrality (MCC)).
 *
 * Param-bearing (`hub_genes`: top_n). Renders summary cards, the ranked hub table (rank, gene,
 * MCC, and the four individual centralities for transparency) with per-row UniProt links + CSV,
 * the param panel (Redo via reset-from/7), the StageDataSources footer, and a
 * `network_too_small` notice.
 *
 * The stage header, ApprovalBar, and StaleNotice are owned by the StageView shell.
 */

import { useMemo, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig, formatCount } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  HUB_GENES_BOOLEAN_PARAMS,
  HUB_GENES_NUMERIC_PARAMS,
  HUB_GENES_PARAMS,
} from "../../contract";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { HubBarChart } from "@/components/charts/HubBarChart";
import { exportPlotlyAsPng } from "@/lib/chartExport";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Local types for the Stage 7 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type Hub = {
  rank: number;
  target_id: string | null;
  gene_symbol: string;
  degree: number;
  betweenness: number;
  closeness: number;
  eigenvector: number;
  mcc: number;
  source_url: string | null;
};

type Stage7Result = {
  state: "computed";
  hubs: Hub[];
  ranking_metric: string;
  node_count: number;
  top_n: number;
  count: number;
  flags?: string[];
  stale?: boolean;
};

type HubParams = Record<string, number | boolean | string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export const S7_CSV_HEADER =
  "rank,gene_symbol,mcc,degree,betweenness,closeness,eigenvector,source_url";

export function buildS7CsvRows(hubs: Hub[]): unknown[][] {
  return hubs.map((h) => [
    h.rank,
    h.gene_symbol,
    h.mcc,
    h.degree,
    h.betweenness,
    h.closeness,
    h.eigenvector,
    h.source_url,
  ]);
}

// ---------------------------------------------------------------------------
// Stage7View
// ---------------------------------------------------------------------------

export function Stage7View({ data }: { data: AnalysisRead }) {
  const stage7 = data.stage_results?.["7"] as Stage7Result | undefined;
  const hubParams = (data.parameters as Record<string, unknown> | undefined)?.hub_genes as
    | HubParams
    | undefined;

  const qc = useQueryClient();
  const redo = useMutation({
    mutationFn: (changed: HubParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 7 },
        body: { parameters: { "7": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 7");
    },
    onError: (error) => notifyError(error as Problem),
  });

  const gdRef = useRef<HTMLElement | null>(null);

  const hubs = useMemo(() => stage7?.hubs ?? [], [stage7]);
  const csvRows = useMemo(() => buildS7CsvRows(hubs), [hubs]);

  if (!stage7) return null;

  const tooSmall = (stage7.flags ?? []).includes("network_too_small");

  // Column definitions — gene-symbol links use the persisted canonical UniProt URL when present.
  // Numeric columns carry meta.className:"num" for right-aligned tabular display.
  const columns: ColumnDef<Hub>[] = [
    {
      id: "rank",
      header: "Rank",
      enableSorting: true,
      meta: { className: "num" },
      cell: ({ row }) => formatCount(row.original.rank),
    },
    {
      id: "gene",
      header: "Gene",
      enableSorting: true,
      cell: ({ row }) =>
        row.original.source_url ? (
          <ExternalLink href={row.original.source_url}>{row.original.gene_symbol}</ExternalLink>
        ) : (
          <span>{row.original.gene_symbol}</span>
        ),
    },
    {
      id: "mcc",
      header: "MCC",
      enableSorting: true,
      meta: { className: "num" },
      cell: ({ row }) => formatCount(row.original.mcc),
    },
    {
      id: "degree",
      header: "Degree",
      enableSorting: true,
      meta: {
        className: "num",
        info: "Number of direct interaction partners in the network (degree centrality).",
      },
      cell: ({ row }) => formatSig(row.original.degree),
    },
    {
      id: "betweenness",
      header: "Betweenness",
      enableSorting: true,
      meta: {
        className: "num",
        info: "Fraction of shortest paths passing through this node (betweenness centrality).",
      },
      cell: ({ row }) => formatSig(row.original.betweenness),
    },
    {
      id: "closeness",
      header: "Closeness",
      enableSorting: true,
      meta: {
        className: "num",
        info: "Inverse of the average shortest-path distance from this node to all others (closeness centrality).",
      },
      cell: ({ row }) => formatSig(row.original.closeness),
    },
    {
      id: "eigenvector",
      header: "Eigenvector",
      enableSorting: true,
      meta: {
        className: "num",
        info: "Influence score weighting connections by neighbour importance (eigenvector centrality).",
      },
      cell: ({ row }) => formatSig(row.original.eigenvector),
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      <StageDataSources stage={7} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={formatCount(stage7.node_count)}
          label="network nodes"
          ariaLabel={`${stage7.node_count} nodes`}
        />
        <StageSummaryCard
          value={formatCount(hubs.length)}
          label="hubs reported"
          ariaLabel={`${hubs.length} hubs`}
        />
        <StageSummaryCard
          value={stage7.ranking_metric}
          label="ranking metric"
          ariaLabel={`metric ${stage7.ranking_metric}`}
          muted
        />
      </div>

      {tooSmall && (
        <p className="text-muted-foreground text-sm" role="status">
          The network is small or sparse. Centrality ranking is unreliable on trivial topology.
        </p>
      )}

      {/* Hub bar chart — tabbed Plotly centrality bars (shown once hubs exist) */}
      {hubs.length > 0 && (
        <ChartFrame
          title="Hub genes by centrality"
          filename="hub_genes.png"
          onExport={async () => {
            if (gdRef.current)
              await exportPlotlyAsPng(gdRef.current, { filename: "hub_genes.png" });
          }}
        >
          <HubBarChart
            hubs={hubs.map((h) => ({
              gene_symbol: h.gene_symbol,
              mcc: h.mcc,
              degree: h.degree,
              betweenness: h.betweenness,
              closeness: h.closeness,
              eigenvector: h.eigenvector,
            }))}
            onGraphDiv={(gd) => (gdRef.current = gd)}
          />
        </ChartFrame>
      )}

      {/* Hub-ranking table card */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <CsvDownloadButton
              header={S7_CSV_HEADER}
              rows={csvRows}
              filename="hubs.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <DataTable columns={columns} data={hubs} />
        </CardContent>
      </Card>

      {/* Hub-ranking param panel */}
      {hubParams && (
        <ParamPanel
          params={hubParams}
          meta={HUB_GENES_PARAMS}
          numericKeys={HUB_GENES_NUMERIC_PARAMS}
          booleanKeys={HUB_GENES_BOOLEAN_PARAMS}
          selectKeys={[]}
          title="Hub-ranking parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      <footer className="text-muted-foreground text-sm">
        <p>
          Ranking: Maximal Clique Centrality (MCC, Chin 2014) on the undirected STRING PPI. Degree,
          betweenness, closeness, and eigenvector centrality (networkx) are reported per target for
          transparency. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
