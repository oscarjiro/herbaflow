import { describe, expect, it } from "vitest";
import { markEntitiesRemoved } from "./optimisticEdit";
import type { AnalysisRead } from "../api/types.gen";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRun(overrides: Record<string, unknown> = {}): AnalysisRead {
  return {
    analysis_id: "r1",
    status: "awaiting_approval",
    current_stage: 1,
    parameters: {},
    stage_results: {},
    stage_state: {},
    ...overrides,
  } as unknown as AnalysisRead;
}

type CompoundRow = { compound_id: string; tag: string };
type TargetRow = { target_id: string; tag: string };

function getCompounds(run: AnalysisRead, stageKey: string): CompoundRow[] {
  const sr = run.stage_results as Record<string, Record<string, unknown>> | undefined;
  const stage = sr?.[stageKey];
  if (!stage) throw new Error(`stage_results["${stageKey}"] missing`);
  return stage["compounds"] as CompoundRow[];
}

function getTargets(run: AnalysisRead, stageKey: string): TargetRow[] {
  const sr = run.stage_results as Record<string, Record<string, unknown>> | undefined;
  const stage = sr?.[stageKey];
  if (!stage) throw new Error(`stage_results["${stageKey}"] missing`);
  return stage["targets"] as TargetRow[];
}

// ---------------------------------------------------------------------------
// Stage 1 — compounds
// ---------------------------------------------------------------------------

describe("markEntitiesRemoved — stage 1 (compounds)", () => {
  it("marks matching compound rows as user-removed", () => {
    const run = makeRun({
      stage_results: {
        "1": {
          compounds: [
            { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
            { compound_id: "c2", canonical_name: "Berberine", tag: "computed" },
          ],
        },
      },
    });

    const result = markEntitiesRemoved(run, 1, ["c1"]);
    const [first, second] = getCompounds(result, "1");

    expect(first?.tag).toBe("user-removed");
    expect(second?.tag).toBe("computed");
  });

  it("leaves non-matching rows unchanged", () => {
    const run = makeRun({
      stage_results: {
        "1": {
          compounds: [
            { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
            { compound_id: "c2", canonical_name: "Berberine", tag: "computed" },
          ],
        },
      },
    });

    const result = markEntitiesRemoved(run, 1, ["c2"]);
    const [first, second] = getCompounds(result, "1");

    expect(first?.tag).toBe("computed"); // c1 untouched
    expect(second?.tag).toBe("user-removed");
  });

  it("does not mutate the input run", () => {
    const run = makeRun({
      stage_results: {
        "1": {
          compounds: [{ compound_id: "c1", canonical_name: "Curcumin", tag: "computed" }],
        },
      },
    });

    markEntitiesRemoved(run, 1, ["c1"]);

    // The original run's compound tag must still be "computed"
    const [first] = getCompounds(run, "1");
    expect(first?.tag).toBe("computed");
  });
});

// ---------------------------------------------------------------------------
// Stage 3 — targets
// ---------------------------------------------------------------------------

describe("markEntitiesRemoved — stage 3 (targets)", () => {
  it("marks matching target rows as user-removed", () => {
    const run = makeRun({
      stage_results: {
        "3": {
          targets: [
            { target_id: "t1", canonical_name: "TP53", tag: "computed" },
            { target_id: "t2", canonical_name: "PPARG", tag: "computed" },
          ],
        },
      },
    });

    const result = markEntitiesRemoved(run, 3, ["t1"]);
    const [first, second] = getTargets(result, "3");

    expect(first?.tag).toBe("user-removed");
    expect(second?.tag).toBe("computed");
  });

  it("does not mutate the input run", () => {
    const run = makeRun({
      stage_results: {
        "3": {
          targets: [{ target_id: "t1", canonical_name: "TP53", tag: "computed" }],
        },
      },
    });

    markEntitiesRemoved(run, 3, ["t1"]);

    const [first] = getTargets(run, "3");
    expect(first?.tag).toBe("computed");
  });
});

// ---------------------------------------------------------------------------
// Stage 4 — targets
// ---------------------------------------------------------------------------

describe("markEntitiesRemoved — stage 4 (targets)", () => {
  it("marks matching target rows as user-removed", () => {
    const run = makeRun({
      stage_results: {
        "4": {
          targets: [
            { target_id: "t1", canonical_name: "BRCA1", tag: "computed" },
            { target_id: "t2", canonical_name: "AKT1", tag: "user-added" },
          ],
        },
      },
    });

    const result = markEntitiesRemoved(run, 4, ["t2"]);
    const [first, second] = getTargets(result, "4");

    expect(first?.tag).toBe("computed"); // untouched
    expect(second?.tag).toBe("user-removed");
  });

  it("does not mutate the input run", () => {
    const run = makeRun({
      stage_results: {
        "4": {
          targets: [{ target_id: "t1", canonical_name: "BRCA1", tag: "computed" }],
        },
      },
    });

    markEntitiesRemoved(run, 4, ["t1"]);

    const [first] = getTargets(run, "4");
    expect(first?.tag).toBe("computed");
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe("markEntitiesRemoved — edge cases", () => {
  it("returns the run unchanged for an unknown stage", () => {
    const run = makeRun({
      stage_results: {
        "2": { some_data: true },
      },
    });

    const result = markEntitiesRemoved(run, 2, ["some-id"]);
    expect(result).toBe(run); // same reference — no copy made
  });

  it("returns the run unchanged when the stage result is missing", () => {
    const run = makeRun({ stage_results: {} });

    const result = markEntitiesRemoved(run, 3, ["t1"]);
    expect(result).toBe(run);
  });

  it("returns the run unchanged when the entity list is absent", () => {
    const run = makeRun({
      stage_results: {
        "3": { count: 0 }, // no `targets` key
      },
    });

    const result = markEntitiesRemoved(run, 3, ["t1"]);
    expect(result).toBe(run);
  });

  it("handles an empty ids array (marks nothing)", () => {
    const run = makeRun({
      stage_results: {
        "1": {
          compounds: [{ compound_id: "c1", canonical_name: "Curcumin", tag: "computed" }],
        },
      },
    });

    const result = markEntitiesRemoved(run, 1, []);
    const [first] = getCompounds(result, "1");
    expect(first?.tag).toBe("computed");
  });
});
