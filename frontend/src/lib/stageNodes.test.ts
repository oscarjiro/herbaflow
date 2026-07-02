import { describe, expect, it } from "vitest";
import type { AnalysisRead } from "@/api/types.gen";
import { nodeState, nodeSub, isNavigable } from "@/lib/stageNodes";

const run = (over: Partial<AnalysisRead>): AnalysisRead =>
  ({
    analysis_id: "r",
    status: "stage_3_awaiting_approval",
    current_stage: 3,
    stage_state: {},
    stage_results: {},
    ...over,
  }) as unknown as AnalysisRead;

describe("stageNodes", () => {
  it("marks a reached stage with results as done", () => {
    const data = run({ stage_results: { "1": { count: 5 } } });
    expect(nodeState("compounds", data)).toBe("done");
    expect(nodeSub("compounds", "done", true, data)).toBe("5 found");
  });

  it("marks the running stage", () => {
    const data = run({ status: "stage_3_running", current_stage: 3 });
    expect(nodeState("targets", data)).toBe("running");
  });

  it("marks the failed stage on a failed run", () => {
    const data = run({ status: "failed", current_stage: 3 });
    expect(nodeState("targets", data)).toBe("failed");
    expect(nodeSub("targets", "failed", false, data)).toBe("Failed");
  });

  it("marks a reached-but-empty stage as blocked", () => {
    const data = run({ current_stage: 6, stage_results: { "6": { count: 0 } } });
    expect(nodeState("ppi", data)).toBe("blocked");
  });

  it("marks an unreached stage as locked, N/A its sub", () => {
    const data = run({ current_stage: 1, stage_results: {} });
    expect(nodeState("hubs", data)).toBe("locked");
    expect(nodeSub("hubs", "locked", false, data)).toBe("Locked");
  });

  it("navigable includes done/active/running/blocked/failed, not locked", () => {
    expect(isNavigable("done")).toBe(true);
    expect(isNavigable("failed")).toBe(true);
    expect(isNavigable("locked")).toBe(false);
    expect(isNavigable("not_applicable")).toBe(false);
  });
});
