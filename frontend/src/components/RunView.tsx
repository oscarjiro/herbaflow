import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type cytoscape from "cytoscape";
import { advanceAnalysis } from "../api/sdk.gen";
import { getCtpGraphOptions } from "../api/@tanstack/react-query.gen";
import type { CtpGraph, CtpGraphNode, CtpGraphEdge, GetCtpGraphResponse } from "../api/types.gen";
import { useAnalysisStatus } from "../hooks/useAnalysisStatus";
import { useEntitySubjects } from "../hooks/useEntitySubjects";
import { useStaleState } from "../hooks/useStaleState";
import { runHasCompounds } from "../lib/entities";
import { useChartColors } from "../lib/chartTheme";
import { NetworkGraph } from "./charts/NetworkGraph";
import { notifyError } from "../lib/toast";
import { humanizeProblem, type Problem } from "../lib/problem";
import { formatRunStatus } from "../lib/runStatus";
import { StageRunningSkeleton } from "./stages/StageRunningSkeleton";
import { ApprovalBar } from "./stages/ApprovalBar";
import { Stage1View } from "./stages/Stage1View";
import { Stage2View } from "./stages/Stage2View";
import { Stage3View } from "./stages/Stage3View";
import { Stage4View } from "./stages/Stage4View";
import { Stage5View } from "./stages/Stage5View";
import { Stage6View } from "./stages/Stage6View";
import { Stage7View } from "./stages/Stage7View";
import { Stage8View } from "./stages/Stage8View";
import { StaleNotice } from "./stages/StaleNotice";
import { DownloadResults } from "./DownloadResults";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Eyebrow } from "@/components/ui/editorial";
import { StepperRail } from "@/components/ui/StepperRail";

/** Returns true when the run is settled (not actively executing a stage). */
function isSettled(status: string | null | undefined): boolean {
  if (!status) return false;
  return status.endsWith("awaiting_approval") || status === "complete" || status === "failed";
}

// ---------------------------------------------------------------------------
// CTP graph helpers
// ---------------------------------------------------------------------------

/**
 * Build a flat Cytoscape elements array from the typed CTP graph.
 * Nodes carry id/label/type/hub; edges carry id/source/target/interaction.
 */
function buildCtpElements(graph: CtpGraph): cytoscape.ElementDefinition[] {
  const nodes: cytoscape.ElementDefinition[] = (graph.nodes as CtpGraphNode[]).map((n) => ({
    data: { id: n.id, label: n.label, type: n.type, hub: n.is_hub },
  }));
  const edges: cytoscape.ElementDefinition[] = (graph.edges as CtpGraphEdge[]).map((e, i) => ({
    data: { id: `e-${i}`, source: e.source, target: e.target, interaction: e.interaction },
  }));
  return [...nodes, ...edges];
}

/** Build the Cytoscape stylesheet for the CTP graph from resolved hf-* color strings. */
function buildCtpStylesheet(colors: ReturnType<typeof useChartColors>): cytoscape.StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        color: colors.fg1,
        "font-size": 9,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 2,
        width: 20,
        height: 20,
      },
    },
    {
      selector: 'node[type = "compound"]',
      style: {
        "background-color": colors.terracotta,
        shape: "ellipse",
      },
    },
    {
      selector: 'node[type = "target"]',
      style: {
        "background-color": colors.sage,
        shape: "ellipse",
      },
    },
    {
      selector: 'node[type = "target"][hub = "true"]',
      style: {
        "background-color": colors.sageDeep,
        width: 30,
        height: 30,
      },
    },
    {
      selector: 'node[type = "pathway"]',
      style: {
        "background-color": colors.info,
        shape: "round-rectangle",
      },
    },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        opacity: 0.6,
      },
    },
    {
      selector: 'edge[interaction = "compound-target"]',
      style: {
        "line-color": colors.border,
        "line-style": "solid",
      },
    },
    {
      selector: 'edge[interaction = "target-pathway"]',
      style: {
        "line-color": colors.fg3,
        "line-style": "dashed",
      },
    },
  ] as cytoscape.StylesheetJson;
}

type Stage1Data = {
  count?: number;
  compounds?: { compound_id: string; canonical_name?: string | null; tag?: string }[];
  state?: string;
};

export function RunView({ analysisId, onReset }: { analysisId: string; onReset?: () => void }) {
  const { data, isError, error } = useAnalysisStatus(analysisId);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: async () => advanceAnalysis({ path: { analysis_id: analysisId } }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });
  const { plant: plantDisplay, disease: diseaseDisplay } = useEntitySubjects(data);
  const colors = useChartColors();

  const ctpEnabled = data?.status === "complete" && runHasCompounds(data);
  const ctpQuery = useQuery({
    ...getCtpGraphOptions({ path: { analysis_id: analysisId } }),
    enabled: ctpEnabled,
  });

  const ctpGraph = (ctpQuery.data as GetCtpGraphResponse | undefined) ?? null;
  const ctpElements = useMemo(() => (ctpGraph ? buildCtpElements(ctpGraph) : []), [ctpGraph]);
  const ctpStylesheet = useMemo(() => buildCtpStylesheet(colors), [colors]);

  if (!data) {
    if (isError) {
      return (
        <div
          role="alert"
          className="border-hf-danger/30 bg-hf-danger-soft/20 mx-auto max-w-lg rounded-[var(--radius-3)] border p-6 text-sm"
        >
          <p className="text-hf-fg-1 font-medium">Could not load analysis status</p>
          <p className="text-hf-fg-2 mt-1">{humanizeProblem(error as Problem)} Retrying...</p>
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-3 p-6">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
    );
  }

  // stage1 is still used below for the inline (unsettled) fallback rendering and ApprovalBar.
  const stage1 = data.stage_results?.["1"] as Stage1Data | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  // Derive the actively-running stage from status like "stage_3_running".
  const runningStageMatch = /^stage_(\d+)_running$/.exec(data.status ?? "");
  const runningStage = runningStageMatch ? Number(runningStageMatch[1]) : null;

  return (
    <div className="lg:grid lg:grid-cols-[16rem_1fr] lg:gap-8">
      {/* Left rail — sticky on large screens, horizontal on small */}
      <aside className="mb-6 self-start lg:sticky lg:top-6 lg:mb-0">
        <StepperRail data={data} />
      </aside>

      {/* Right column — main content */}
      <section className="flex min-w-0 flex-col gap-6">
        {/* Editorial header */}
        <header className="flex flex-col gap-2">
          <Eyebrow>ANALYSIS</Eyebrow>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Run <span className="text-hf-fg-3 font-mono text-base">{analysisId}</span>
            </h1>
            <Badge variant="outline" className="capitalize">
              {formatRunStatus(data.status)}
            </Badge>
          </div>
          <p className="text-hf-fg-3 text-sm">
            Plant: {plantDisplay} · Disease: {diseaseDisplay}
          </p>
        </header>

        <DownloadResults
          status={data.status}
          analysisId={analysisId}
          hasCompounds={runHasCompounds(data)}
        />

        {data.status === "complete" &&
          runHasCompounds(data) &&
          (ctpQuery.isPending ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-[420px] w-full" />
            </div>
          ) : ctpGraph && ctpGraph.nodes.length > 0 ? (
            <NetworkGraph
              title="Compound, target and pathway network"
              filename="ctp_network.png"
              elements={ctpElements}
              stylesheet={ctpStylesheet}
            />
          ) : null)}

        {data.status === "failed" && (
          <div
            role="alert"
            className="border-hf-danger/30 bg-hf-danger-soft/20 flex flex-col gap-3 rounded-[var(--radius-3)] border p-4"
          >
            <p className="text-hf-fg-1 text-sm">{data.error_message}</p>
            {onReset && (
              <Button variant="outline" size="sm" onClick={onReset}>
                Back to setup
              </Button>
            )}
          </div>
        )}

        {stage1 && (
          <>
            {isSettled(data.status) || stage1.state === "not_applicable" ? (
              <Stage1View data={data} />
            ) : (
              <>
                <h2 className="text-lg font-semibold">
                  Compounds ({stage1.compounds?.length ?? 0})
                </h2>
                <ul className="text-hf-fg-2 list-disc pl-5 text-sm">
                  {stage1.compounds?.map((c, i) => (
                    <li key={i}>{c.canonical_name}</li>
                  ))}
                </ul>
              </>
            )}
            {/* ApprovalBar self-gates to the current stage, so stacked views show a single button. */}
            {rerunFrom === 1 && <StaleNotice analysisId={analysisId} fromStage={rerunFrom} />}
            <ApprovalBar
              stage={1}
              status={data.status}
              currentStage={data.current_stage}
              disabled={(stage1.count ?? 0) === 0 || anyStale}
              disabledReason={
                anyStale
                  ? "Run the updated step before continuing."
                  : "No compounds found. Add one to continue."
              }
              pending={advance.isPending}
              onApprove={() => advance.mutate()}
            />
          </>
        )}

        {Boolean(data.stage_results?.["2"]) && <Stage2View data={data} />}

        {Boolean(data.stage_results?.["3"]) && <Stage3View data={data} />}

        {Boolean(data.stage_results?.["4"]) && <Stage4View data={data} />}

        {Boolean(data.stage_results?.["5"]) && <Stage5View data={data} />}

        {Boolean(data.stage_results?.["6"]) && <Stage6View data={data} />}

        {Boolean(data.stage_results?.["7"]) && <Stage7View data={data} />}

        {Boolean(data.stage_results?.["8"]) && <Stage8View data={data} />}

        {runningStage != null && !data.stage_results?.[String(runningStage)] && (
          <StageRunningSkeleton stage={runningStage} />
        )}
      </section>
    </div>
  );
}
