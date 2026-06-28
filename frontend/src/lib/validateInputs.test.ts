import { describe, expect, test } from "vitest";
import { distinctInputs } from "./validateInputs";

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
