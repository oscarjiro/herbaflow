import type { AnalysisRead } from "@/api/types.gen";

export type StageSlug =
  | "inputs"
  | "compounds"
  | "adme"
  | "targets"
  | "disease-targets"
  | "overlap"
  | "ppi"
  | "hubs"
  | "enrichment"
  | "final";

// Full ordered set: Inputs bookend → the eight pipeline stages → Final bookend.
// Used for routing, guards and furthest-reached logic (inputs is still a valid,
// deep-linkable route — it is just not shown as a trail step, see TRAIL_SLUGS).
export const STAGE_SLUGS: StageSlug[] = [
  "inputs",
  "compounds",
  "adme",
  "targets",
  "disease-targets",
  "overlap",
  "ppi",
  "hubs",
  "enrichment",
  "final",
];

// The slugs the visible trail renders: the eight stages + the Final bookend.
// Inputs is part of setup, not a pipeline step, so it is omitted from the trail.
export const TRAIL_SLUGS: StageSlug[] = STAGE_SLUGS.filter((s) => s !== "inputs");

const SLUG_TO_STAGE: Record<StageSlug, number | null> = {
  inputs: null,
  compounds: 1,
  adme: 2,
  targets: 3,
  "disease-targets": 4,
  overlap: 5,
  ppi: 6,
  hubs: 7,
  enrichment: 8,
  final: null,
};

export function slugToStage(slug: StageSlug): number | null {
  return SLUG_TO_STAGE[slug];
}

export function stageToSlug(n: number): StageSlug | null {
  const found = (Object.keys(SLUG_TO_STAGE) as StageSlug[]).find((s) => SLUG_TO_STAGE[s] === n);
  return found ?? null;
}

export function isValidStageSlug(slug: string): slug is StageSlug {
  return Object.prototype.hasOwnProperty.call(SLUG_TO_STAGE, slug);
}

export function isSlugApplicable(slug: StageSlug, run: AnalysisRead): boolean {
  const n = slugToStage(slug);
  if (n === null) return true; // bookends always apply
  return run.stage_state?.[String(n)] !== "not_applicable";
}

export function isSlugReached(slug: StageSlug, run: AnalysisRead): boolean {
  if (slug === "inputs") return true;
  if (slug === "final") return run.status === "complete";
  const n = slugToStage(slug);
  if (n === null) return false;
  if (run.stage_results?.[String(n)]) return true;
  const current = run.current_stage;
  return current != null && n <= current;
}

export function furthestReachedSlug(run: AnalysisRead): StageSlug {
  let furthest: StageSlug = "inputs";
  for (const slug of STAGE_SLUGS) {
    if (isSlugApplicable(slug, run) && isSlugReached(slug, run)) furthest = slug;
  }
  return furthest;
}
