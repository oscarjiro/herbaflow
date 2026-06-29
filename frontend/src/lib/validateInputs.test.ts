import { describe, expect, test } from "vitest";
import { distinctInputs, distinctInputsWithOrigin } from "./validateInputs";

describe("distinctInputs", () => {
  test("deduplicates identical values, preserving first-seen order", () => {
    const result = distinctInputs([{ value: "a" }, { value: "b" }, { value: "a" }]);
    expect(result).toEqual([{ value: "a" }, { value: "b" }]);
  });

  test("trims whitespace from values before comparing", () => {
    // "  a  " trims to "a"; the later bare "a" is a duplicate and is dropped
    const result = distinctInputs([{ value: "  a  " }, { value: "b" }, { value: "a" }]);
    expect(result).toEqual([{ value: "  a  " }, { value: "b" }]);
  });

  test("drops blank and whitespace-only entries", () => {
    const result = distinctInputs([{ value: "" }, { value: "a" }, { value: "  " }]);
    expect(result).toEqual([{ value: "a" }]);
  });

  test("preserves extra fields from the first-seen object", () => {
    // StpDialog passes { type: "uniprot", value } — the type field must survive
    const result = distinctInputs([
      { value: "P04637", type: "uniprot" as const },
      { value: "P04637", type: "uniprot" as const },
    ]);
    expect(result).toEqual([{ value: "P04637", type: "uniprot" }]);
  });

  test("returns empty array for empty input", () => {
    expect(distinctInputs([])).toEqual([]);
  });

  test("preserves first-seen order, not insertion order of duplicates", () => {
    const result = distinctInputs([{ value: "c" }, { value: "a" }, { value: "b" }, { value: "a" }]);
    expect(result).toEqual([{ value: "c" }, { value: "a" }, { value: "b" }]);
  });

  test("all-whitespace-only list returns empty array", () => {
    const result = distinctInputs([{ value: "  " }, { value: "\t" }, { value: "" }]);
    expect(result).toEqual([]);
  });
});

describe("distinctInputsWithOrigin", () => {
  test("records the 1-based original line of each distinct entry's first occurrence", () => {
    // Lines:      1     2(blank) 3       4(dup)   5
    const { items, lines } = distinctInputsWithOrigin([
      { value: "EGFR" },
      { value: "" },
      { value: "BADGENE" },
      { value: "EGFR" },
      { value: "OTHER" },
    ]);
    expect(items).toEqual([{ value: "EGFR" }, { value: "BADGENE" }, { value: "OTHER" }]);
    // EGFR first on line 1, BADGENE on line 3, OTHER on line 5 — blank/dup do not shift them.
    expect(lines).toEqual([1, 3, 5]);
  });

  test("items match distinctInputs and lines are aligned by index", () => {
    const inputs = [{ value: "a" }, { value: "a" }, { value: "b" }];
    const { items, lines } = distinctInputsWithOrigin(inputs);
    expect(items).toEqual(distinctInputs(inputs));
    expect(lines).toEqual([1, 3]);
  });
});
