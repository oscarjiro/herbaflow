import { expect, test } from "vitest";
import { humanizeLabel, humanizeValue } from "./labels";

test("humanizes param keys", () => {
  expect(humanizeLabel("min_term_size")).toBe("Minimum term size");
  expect(humanizeLabel("significance_threshold")).toBe("Significance threshold (corrected p ≤)");
  expect(humanizeLabel("unknown_key")).toBe("unknown_key");
});

test("humanizes enum values", () => {
  expect(humanizeValue("functional")).toBe("Functional");
  expect(humanizeValue("g_SCS")).toBe("g:SCS");
});
