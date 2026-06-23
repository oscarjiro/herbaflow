import { expect, test } from "vitest";
import { humanizeLabel, humanizeValue, STAGE_LABELS, stageLabel } from "./labels";
import {
  ADME_NUMERIC_PARAMS,
  ADME_BOOLEAN_PARAMS,
  TARGET_NUMERIC_PARAMS,
  DISEASE_TARGETS_NUMERIC_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_BOOLEAN_PARAMS,
  PPI_SELECT_PARAMS,
  HUB_GENES_NUMERIC_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
  ENRICHMENT_ARRAY_PARAMS,
} from "./index";

// Every parameter the ParamPanel renders must have a human label; a raw key
// (e.g. "max_mw") leaking to the UI is the bug this guards against.
const ALL_PARAM_KEYS: string[] = [
  ...ADME_NUMERIC_PARAMS,
  ...ADME_BOOLEAN_PARAMS,
  ...TARGET_NUMERIC_PARAMS,
  ...DISEASE_TARGETS_NUMERIC_PARAMS,
  ...PPI_NUMERIC_PARAMS,
  ...PPI_BOOLEAN_PARAMS,
  ...PPI_SELECT_PARAMS,
  ...HUB_GENES_NUMERIC_PARAMS,
  ...ENRICHMENT_NUMERIC_PARAMS,
  ...ENRICHMENT_BOOLEAN_PARAMS,
  ...ENRICHMENT_SELECT_PARAMS,
  ...ENRICHMENT_ARRAY_PARAMS,
];

test.each(ALL_PARAM_KEYS)("humanizeLabel(%s) never leaks the raw key", (key) => {
  const label = humanizeLabel(key);
  expect(label).not.toBe(key);
  expect(label.length).toBeGreaterThan(0);
});

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
