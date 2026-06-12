import { describe, expect, it } from "vitest";
import { atMinEntities, isUserRemoved } from "./entities";

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
