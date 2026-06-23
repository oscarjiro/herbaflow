import { describe, expect, it } from "vitest";
import { atMinEntities, isUserRemoved, runHasCompounds, runHasCtp } from "./entities";

describe("isUserRemoved", () => {
  it("is true only for the user-removed tag", () => {
    expect(isUserRemoved("user-removed")).toBe(true);
    expect(isUserRemoved("user-added")).toBe(false);
    expect(isUserRemoved("computed")).toBe(false);
    expect(isUserRemoved(undefined)).toBe(false);
  });
});

describe("atMinEntities", () => {
  it("is true at one-or-fewer visible entities", () => {
    expect(atMinEntities(1)).toBe(true);
    expect(atMinEntities(0)).toBe(true);
    expect(atMinEntities(2)).toBe(false);
  });
});

describe("runHasCompounds", () => {
  it("is false for manual_targets, true otherwise", () => {
    expect(runHasCompounds({ parameters: { input_modes: { plant: "manual_targets" } } })).toBe(
      false,
    );
    expect(runHasCompounds({ parameters: { input_modes: { plant: "selection" } } })).toBe(true);
    expect(runHasCompounds({ parameters: { input_modes: { plant: "manual_compounds" } } })).toBe(
      true,
    );
    expect(runHasCompounds({})).toBe(true);
    expect(runHasCompounds(null)).toBe(true);
  });
});

describe("runHasCtp", () => {
  const withCounts = (overlap: number, terms: number, plant = "selection") => ({
    parameters: { input_modes: { plant } },
    stage_results: {
      "5": { count: overlap },
      "8": { count: terms },
    },
  });

  it("is false when plant mode is manual_targets (no compounds)", () => {
    expect(runHasCtp(withCounts(5, 3, "manual_targets"))).toBe(false);
  });

  it("is false when Stage-8 term count is 0", () => {
    expect(runHasCtp(withCounts(5, 0))).toBe(false);
  });

  it("is false when Stage-5 overlap count is 0", () => {
    expect(runHasCtp(withCounts(0, 3))).toBe(false);
  });

  it("is true when compounds, overlap > 0, and terms > 0", () => {
    expect(runHasCtp(withCounts(5, 3))).toBe(true);
    expect(runHasCtp(withCounts(1, 1, "manual_compounds"))).toBe(true);
  });

  it("is false when stage_results are absent", () => {
    expect(runHasCtp({ parameters: { input_modes: { plant: "selection" } } })).toBe(false);
    expect(runHasCtp(null)).toBe(false);
    expect(runHasCtp(undefined)).toBe(false);
  });
});
