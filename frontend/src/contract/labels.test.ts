import { expect, test } from "vitest";
import { humanizeLabel, humanizeValue, STAGE_LABELS, stageLabel } from "./labels";

test("humanizes param keys", () => {
  expect(humanizeLabel("min_term_size")).toBe("Minimum term size");
  expect(humanizeLabel("significance_threshold")).toBe("Significance threshold (corrected p ≤)");
  expect(humanizeLabel("correction")).toBe("Correction");
  expect(humanizeLabel("network_type")).toBe("Network type");
  expect(humanizeLabel("top_n")).toBe("Top N");
  expect(humanizeLabel("min_confidence")).toBe("Minimum confidence");
  expect(humanizeLabel("min_score")).toBe("Minimum score");
  expect(humanizeLabel("no_iea")).toBe("Exclude electronic annotations (IEA)");
  expect(humanizeLabel("unknown_key")).toBe("unknown_key");
});

test("STAGE_LABELS has exactly 8 entries", () => {
  expect(STAGE_LABELS).toHaveLength(8);
});

test("stageLabel returns the correct label for valid stage numbers", () => {
  expect(stageLabel(7)).toBe("Hub genes");
  expect(stageLabel(1)).toBe("Compounds");
  expect(stageLabel(8)).toBe("Pathway enrichment");
});

test("stageLabel falls back to Step N for out-of-range stage", () => {
  expect(stageLabel(99)).toBe("Step 99");
  expect(stageLabel(0)).toBe("Step 0");
});

test("humanizes enum values", () => {
  expect(humanizeValue("functional")).toBe("Functional");
  expect(humanizeValue("physical")).toBe("Physical");
  expect(humanizeValue("g_SCS")).toBe("g:SCS");
  expect(humanizeValue("fdr")).toBe("FDR");
  expect(humanizeValue("bonferroni")).toBe("Bonferroni");
  expect(humanizeValue("REAC")).toBe("Reactome");
  expect(humanizeValue("WP")).toBe("WikiPathways");
});
