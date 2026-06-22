import { Link } from "@tanstack/react-router";
import {
  Activity,
  Check,
  Crosshair,
  Droplets,
  FileCheck,
  FlaskConical,
  GitCompareArrows,
  Hexagon,
  Loader2,
  ListTree,
  Minus,
  Share2,
  Sprout,
} from "lucide-react";
import type { AnalysisRead } from "@/api/types.gen";
import { stageLabel } from "@/contract/labels";
import {
  TRAIL_SLUGS,
  isSlugApplicable,
  isSlugReached,
  slugToStage,
  type StageSlug,
} from "@/lib/stageRoutes";
import { cn } from "@/lib/cn";

function slugLabel(slug: StageSlug): string {
  if (slug === "inputs") return "Inputs";
  if (slug === "final") return "Final";
  const n = slugToStage(slug);
  return n != null ? stageLabel(n) : slug;
}

const SLUG_ICON: Record<StageSlug, typeof Sprout> = {
  inputs: Sprout,
  compounds: FlaskConical,
  adme: Droplets,
  targets: Crosshair,
  "disease-targets": Activity,
  overlap: GitCompareArrows,
  ppi: Share2,
  hubs: Hexagon,
  enrichment: ListTree,
  final: FileCheck,
};

type NodeState = "done" | "running" | "active" | "locked" | "not_applicable" | "blocked";

function nodeState(slug: StageSlug, data: AnalysisRead, activeSlug?: StageSlug): NodeState {
  if (!isSlugApplicable(slug, data)) return "not_applicable";
  const n = slugToStage(slug);
  const runningMatch = /^stage_(\d+)_running$/.exec(data.status ?? "");
  if (n != null && runningMatch && Number(runningMatch[1]) === n) return "running";
  if (slug === activeSlug) return "active";
  if (isSlugReached(slug, data)) {
    const result =
      n != null ? (data.stage_results?.[String(n)] as { count?: number } | undefined) : undefined;
    if (result && result.count === 0) return "blocked";
    return "done";
  }
  return "locked";
}

export function StepperRail({
  data,
  analysisId,
  activeSlug,
  className,
  markers = "icon",
}: {
  data: AnalysisRead;
  analysisId: string;
  activeSlug?: StageSlug;
  className?: string;
  markers?: "icon" | "number";
}) {
  return (
    <nav aria-label="Pipeline steps" className={cn("w-full", className)}>
      <ol className="scroll flex flex-row gap-1 overflow-x-auto lg:flex-col lg:gap-1.5 lg:overflow-x-visible">
        {TRAIL_SLUGS.map((slug) => {
          const state = nodeState(slug, data, activeSlug);
          const navigable =
            state === "done" || state === "active" || state === "running" || state === "blocked";
          const label = slugLabel(slug);
          const Icon = SLUG_ICON[slug];
          const n = slugToStage(slug);
          const showProgress =
            state === "running" && data.progress != null && n != null && data.progress.stage === n;

          const marker = (
            <span
              className={cn(
                "border-hf-border flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs",
                state === "active" && "ring-hf-sage-deep border-current ring-2",
                state === "done" && "bg-hf-fg-1 border-hf-fg-1 text-hf-bg",
                state === "blocked" && "border-hf-warning text-hf-warning",
                state === "locked" && "opacity-50",
                state === "not_applicable" && "opacity-40",
              )}
              data-state={state}
              aria-hidden="true"
            >
              {state === "running" ? (
                <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" />
              ) : state === "done" ? (
                <Check className="size-3.5" />
              ) : state === "not_applicable" ? (
                <Minus className="size-3.5" />
              ) : markers === "number" && n != null ? (
                n
              ) : (
                <Icon className="size-3.5" />
              )}
            </span>
          );

          const body = (
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="truncate">{label}</span>
              {showProgress && (
                <span className="text-hf-fg-4 font-mono text-[0.65rem]">
                  Working {data.progress!.processed} / {data.progress!.total}
                </span>
              )}
              {state === "not_applicable" && (
                <span className="text-hf-fg-4 font-mono text-[0.65rem]">Not applicable</span>
              )}
              {state === "blocked" && (
                <span className="text-hf-warning font-mono text-[0.65rem]">No results</span>
              )}
            </span>
          );

          const itemClass = cn(
            "flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
            state === "active" && "bg-hf-surface text-hf-fg-1 font-semibold",
            state === "done" && "text-hf-fg-2",
            state === "running" && "text-hf-fg-1",
            state === "locked" && "text-hf-fg-3",
            state === "not_applicable" && "text-hf-fg-3 opacity-60",
          );

          if (navigable) {
            return (
              <li key={slug} aria-current={state === "active" ? "step" : undefined}>
                <Link
                  to="/analysis/$id/$stage"
                  params={{ id: analysisId, stage: slug }}
                  className={cn(itemClass, "hover:bg-hf-surface w-full")}
                >
                  {marker}
                  {body}
                </Link>
              </li>
            );
          }
          return (
            <li key={slug} aria-disabled="true" className={cn(itemClass, "cursor-not-allowed")}>
              {marker}
              {body}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
