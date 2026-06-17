import { expect, test } from "vitest";
import { humanizeLabel, humanizeValue } from "./labels";

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

test("humanizes enum values", () => {
  expect(humanizeValue("functional")).toBe("Functional");
  expect(humanizeValue("physical")).toBe("Physical");
  expect(humanizeValue("g_SCS")).toBe("g:SCS");
  expect(humanizeValue("fdr")).toBe("FDR");
  expect(humanizeValue("bonferroni")).toBe("Bonferroni");
});
