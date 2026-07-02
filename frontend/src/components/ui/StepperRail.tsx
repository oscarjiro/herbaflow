import { Link } from "@tanstack/react-router";
import type { AnalysisRead } from "@/api/types.gen";
import { TRAIL_SLUGS, isSlugReached, stageSlugLabel, type StageSlug } from "@/lib/stageRoutes";
import { nodeState, nodeSub, isNavigable } from "@/lib/stageNodes";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Stage icon SVG paths (from analysis.html mockup — stroke, 15×15 viewBox 0 0 24 24)
// ---------------------------------------------------------------------------
const SLUG_ICON_PATH: Record<StageSlug, string> = {
  inputs: "M7 20h10M12 20V8M12 8C12 5 9 3 6 4c0 3 3 5 6 4zM12 10c0-3 3-5 6-4 0 3-3 5-6 4z",
  compounds: "M9 3h6M10 3v6l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V3",
  adme: "M3 5h18l-7 8v6l-4-2v-4z",
  targets: "", // two concentric circles — rendered with <circle> elements
  "disease-targets": "M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z",
  overlap: "", // two overlapping circles — rendered with <circle> elements
  ppi: "", // network dots — rendered separately
  hubs: "M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M19 5l-3 3M8 16l-3 3",
  enrichment: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5M3 17l9 5 9-5",
  final: "M5 3v18M5 4h13l-2.5 4L18 12H5",
};

// Icon renderer — some stages use multiple SVG primitives, not a single <path>
function StageIcon({ slug, className }: { slug: StageSlug; className?: string }) {
  const base = "ic";
  const cls = cn(base, className);

  if (slug === "targets") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    );
  }
  if (slug === "overlap") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none">
        <circle cx="9" cy="12" r="6" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="15" cy="12" r="6" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    );
  }
  if (slug === "ppi") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="6" cy="6" r="2.5" />
        <circle cx="18" cy="7" r="2.5" />
        <circle cx="12" cy="18" r="2.5" />
        <path d="M8 7l8 1M7 8l5 8M16 9l-4 7" />
      </svg>
    );
  }
  if (slug === "hubs") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="12" cy="12" r="3" />
        <path d={SLUG_ICON_PATH[slug]} />
      </svg>
    );
  }
  return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d={SLUG_ICON_PATH[slug]} />
    </svg>
  );
}

// Check SVG (14×14, strokeWidth 2.4)
function CheckIcon() {
  return (
    <svg className="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
      <path d="M5 12l4 4L19 7" />
    </svg>
  );
}

export function StepperRail({
  data,
  analysisId,
  activeSlug,
  className,
  onNavigate,
}: {
  data: AnalysisRead;
  analysisId: string;
  activeSlug?: StageSlug;
  className?: string;
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Pipeline steps" className={cn("trail w-full", className)}>
      <ol>
        {TRAIL_SLUGS.map((slug) => {
          const state = nodeState(slug, data, activeSlug);
          const isReached = isSlugReached(slug, data);
          // A node can be both done AND active (mockup allows co-existence)
          const isDone =
            state === "done" || state === "blocked" || (state === "active" && isReached);
          const isActive = state === "active" || activeSlug === slug;
          const isRunning = state === "running";
          const isLocked = state === "locked";
          const isNA = state === "not_applicable";
          const isFailed = state === "failed";
          const navigable = isNavigable(state);
          const isFinal = slug === "final";
          const label = stageSlugLabel(slug);
          const sub = nodeSub(slug, state, isDone, data);

          const itemClass = cn(
            "trail-item",
            isDone && "is-done",
            isRunning && "is-running",
            isActive && "is-active",
            isLocked && "is-locked",
            isFailed && "is-failed",
            isFinal && "bookend-final",
          );

          const nodeEl = (
            <span className="node" data-state={state} aria-hidden="true">
              <StageIcon slug={slug} />
              <CheckIcon />
            </span>
          );

          const labelEl = (
            <span className="t-label">
              <span className="t-name">{label}</span>
              {sub ? <span className="t-sub">{sub}</span> : null}
              {isNA && !sub ? <span className="t-sub">N/A</span> : null}
            </span>
          );

          if (navigable) {
            return (
              <li key={slug} aria-current={isActive && !isDone ? "step" : undefined}>
                <Link
                  to="/analysis/$id/$stage"
                  params={{ id: analysisId, stage: slug }}
                  className={itemClass}
                  onClick={onNavigate}
                >
                  {nodeEl}
                  {labelEl}
                </Link>
              </li>
            );
          }

          return (
            <li key={slug} aria-disabled={isLocked || isNA ? "true" : undefined}>
              <span className={itemClass}>
                {nodeEl}
                {labelEl}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
