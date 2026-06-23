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

import { useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig } from "../../lib/format";
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
import { ChartFrame } from "@/components/charts/ChartFrame";
import { HubBarChart } from "@/components/charts/HubBarChart";
import { exportPlotlyAsPng } from "@/lib/chartExport";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";

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

const PAGE_SIZES = [10, 20, 50] as const;

const S7_CSV_HEADER = "rank,gene_symbol,mcc,degree,betweenness,closeness,eigenvector,source_url";

function buildS7CsvRows(hubs: Hub[]): unknown[][] {
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

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);
  const gdRef = useRef<HTMLElement | null>(null);

  const hubs = useMemo(() => stage7?.hubs ?? [], [stage7]);
  const csvRows = useMemo(() => buildS7CsvRows(hubs), [hubs]);

  if (!stage7) return null;

  const effectivePageSize = pageSize === "all" ? Math.max(1, hubs.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(hubs.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visible = hubs.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const tooSmall = (stage7.flags ?? []).includes("network_too_small");

  // Column definitions — SAME columns + order as the prior <table>
  const columns: ColumnDef<Hub>[] = [
    {
      id: "rank",
      header: "Rank",
      cell: ({ row }) => row.original.rank,
    },
    {
      id: "gene",
      header: "Gene",
      cell: ({ row }) => {
        const h = row.original;
        return h.source_url ? (
          <a href={h.source_url} target="_blank" rel="noreferrer">
            {h.gene_symbol}
          </a>
        ) : (
          h.gene_symbol
        );
      },
    },
    {
      id: "mcc",
      header: "MCC",
      cell: ({ row }) => row.original.mcc,
    },
    {
      id: "degree",
      header: "Degree",
      cell: ({ row }) => formatSig(row.original.degree),
    },
    {
      id: "betweenness",
      header: "Betweenness",
      cell: ({ row }) => formatSig(row.original.betweenness),
    },
    {
      id: "closeness",
      header: "Closeness",
      cell: ({ row }) => formatSig(row.original.closeness),
    },
    {
      id: "eigenvector",
      header: "Eigenvector",
      cell: ({ row }) => formatSig(row.original.eigenvector),
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      <StageDataSources stage={7} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage7.node_count} nodes`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{stage7.node_count}</span>
          <span className="text-muted-foreground text-xs">network nodes</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${hubs.length} hubs`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{hubs.length}</span>
          <span className="text-muted-foreground text-xs">hubs reported</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`metric ${stage7.ranking_metric}`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage7.ranking_metric}
          </span>
          <span className="text-muted-foreground text-xs">ranking metric</span>
        </div>
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
            <div className="flex items-center gap-2">
              <label htmlFor="t7-page-size" className="text-muted-foreground text-sm">
                Rows per page
              </label>
              <select
                id="t7-page-size"
                className="bg-background rounded border px-2 py-1 text-sm"
                value={pageSize}
                onChange={(e) => {
                  const v = e.target.value;
                  setPageSize(v === "all" ? "all" : Number(v));
                  setPage(0);
                }}
              >
                {PAGE_SIZES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
                <option value="all">All</option>
              </select>
            </div>
            <CsvDownloadButton
              header={S7_CSV_HEADER}
              rows={csvRows}
              filename="hub-genes.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <DataTable columns={columns} data={visible} />
        </CardContent>

        {/* Pagination */}
        {pageSize !== "all" && totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 px-6 pb-4">
            <button
              className="hf-btn text-sm"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span className="text-muted-foreground text-sm">
              Page {currentPage + 1} / {totalPages}
            </span>
            <button
              className="hf-btn text-sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
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
