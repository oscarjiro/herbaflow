import { describe, expect, it } from "vitest";
import { MAX_PLANTS, MODES, modeSchema } from "../src/contract";

describe("contract", () => {
  it("exposes the shared mode vocabulary", () => {
    expect(MODES).toEqual(["auto", "guided"]);
  });

  it("exposes the plant cap", () => {
    expect(MAX_PLANTS).toBe(20);
  });

  it("validates mode values", () => {
    expect(modeSchema.safeParse("auto").success).toBe(true);
    expect(modeSchema.safeParse("bogus").success).toBe(false);
  });
});
