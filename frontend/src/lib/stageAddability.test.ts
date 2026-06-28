import { describe, expect, it } from "vitest";
import type { AnalysisRead } from "@/api/types.gen";
import { canAddWhenEmpty } from "@/lib/stageAddability";

function run(plantMode: string): AnalysisRead {
  return {
    parameters: { input_modes: { plant: plantMode, disease: "selection" } },
  } as unknown as AnalysisRead;
}

describe("canAddWhenEmpty", () => {
  it("stage 1 is always addable", () => {
    expect(canAddWhenEmpty(1, run("manual_targets"))).toBe(true);
  });
  it("stage 3 is addable only when compounds exist", () => {
    expect(canAddWhenEmpty(3, run("selection"))).toBe(true);
    expect(canAddWhenEmpty(3, run("manual_targets"))).toBe(false);
  });
  it("stage 4 is always addable", () => {
    expect(canAddWhenEmpty(4, run("manual_targets"))).toBe(true);
  });
  it("computed/terminal stages are never empty-addable", () => {
    for (const s of [2, 5, 6, 7, 8]) expect(canAddWhenEmpty(s, run("selection"))).toBe(false);
  });
});
