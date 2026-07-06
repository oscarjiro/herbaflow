import { describe, expect, it } from "vitest";
import { METRIC_INFO } from "./metricInfo";

/** Flatten every definition string in the keyed map for sweep-style assertions. */
function allDefinitions(): string[] {
  return Object.values(METRIC_INFO).flatMap((group) => Object.values(group));
}

describe("METRIC_INFO", () => {
  it("exposes representative definitions used across the stage views", () => {
    // A few plumbing spot checks: one column def and one card def per family.
    expect(METRIC_INFO.s2.lipinski).toMatch(/Lipinski/);
    expect(METRIC_INFO.s2.passed).toMatch(/cleared the drug-likeness screen/);
    expect(METRIC_INFO.s4.openTargetsScore).toMatch(/Open Targets/);
    expect(METRIC_INFO.s6.confidence).toMatch(/from 0 to 1/);
    expect(METRIC_INFO.s8.backgroundGenes).toMatch(/comparison set/);
  });

  it("describes Degree as a normalized centrality, not a raw partner count", () => {
    // Accuracy fix: the value is nx.degree_centrality (0..1), not a raw partner count.
    expect(METRIC_INFO.s7.degree).toMatch(/scaled from 0 to 1/);
    expect(METRIC_INFO.s7.degree).not.toMatch(/number of direct interaction partners/i);
  });

  it("describes the unmapped card as a real, meaningful count", () => {
    expect(METRIC_INFO.s6.unmapped).toMatch(/no gene symbol/);
  });

  it("keeps display copy free of em dashes", () => {
    for (const def of allDefinitions()) {
      expect(def).not.toContain("—");
    }
  });

  it("keeps display copy free of internal stage-number vocabulary", () => {
    for (const def of allDefinitions()) {
      expect(def).not.toMatch(/\bStage \d/);
    }
  });
});
