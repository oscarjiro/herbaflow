import type { AnalysisRead } from "@/api/types.gen";
import {
  STAGE_SLUGS, slugToStage, stageToSlug, isValidStageSlug,
  isSlugApplicable, isSlugReached, furthestReachedSlug,
} from "./stageRoutes";

const run = (over: Partial<AnalysisRead>): AnalysisRead =>
  ({ analysis_id: "a", status: "stage_3_awaiting_approval", current_stage: 3,
     stage_results: { "1": {}, "2": {}, "3": {} }, stage_state: {} , ...over } as AnalysisRead);

test("slug map is bijective over the 8 pipeline stages", () => {
  expect(slugToStage("compounds")).toBe(1);
  expect(slugToStage("enrichment")).toBe(8);
  expect(slugToStage("inputs")).toBeNull();
  expect(slugToStage("final")).toBeNull();
  expect(stageToSlug(4)).toBe("disease-targets");
  expect(STAGE_SLUGS[0]).toBe("inputs");
  expect(STAGE_SLUGS[STAGE_SLUGS.length - 1]).toBe("final");
});

test("isValidStageSlug guards unknown slugs", () => {
  expect(isValidStageSlug("compounds")).toBe(true);
  expect(isValidStageSlug("nope")).toBe(false);
});

test("not_applicable stages are not applicable; bookends always applicable", () => {
  const r = run({ stage_state: { "2": "not_applicable" } });
  expect(isSlugApplicable("adme", r)).toBe(false);
  expect(isSlugApplicable("compounds", r)).toBe(true);
  expect(isSlugApplicable("inputs", r)).toBe(true);
  expect(isSlugApplicable("final", r)).toBe(true);
});

test("reached = has result, is/under current stage; final reached only when complete", () => {
  const r = run({});
  expect(isSlugReached("inputs", r)).toBe(true);
  expect(isSlugReached("compounds", r)).toBe(true);
  expect(isSlugReached("targets", r)).toBe(true);
  expect(isSlugReached("overlap", r)).toBe(false);
  expect(isSlugReached("final", r)).toBe(false);
  expect(isSlugReached("final", run({ status: "complete", current_stage: 8 }))).toBe(true);
});

test("furthestReachedSlug points at the deepest reached applicable slug", () => {
  expect(furthestReachedSlug(run({}))).toBe("targets");
  expect(furthestReachedSlug(run({ status: "complete", current_stage: 8 }))).toBe("final");
});
