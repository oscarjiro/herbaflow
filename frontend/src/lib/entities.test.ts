import { describe, expect, it } from "vitest";
import { atMinEntities, isUserRemoved, runHasCompounds } from "./entities";

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
