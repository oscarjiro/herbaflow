import { describe, expect, it } from "vitest";
import {
  MAX_PLANTS,
  MODES,
  modeSchema,
  DISEASE_TARGETS_PARAMS,
  DISEASE_TARGETS_NUMERIC_PARAMS,
} from "../src/contract";

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

describe("disease_targets contract", () => {
  it("derives min_score default and advisory band", () => {
    expect(DISEASE_TARGETS_PARAMS.min_score.default).toBe(0.3);
    expect(DISEASE_TARGETS_PARAMS.min_score.min).toBe(0);
    expect(DISEASE_TARGETS_PARAMS.min_score.max).toBe(1);
    expect(DISEASE_TARGETS_PARAMS.min_score.recommended_min).toBe(0.1);
    expect(DISEASE_TARGETS_PARAMS.min_score.recommended_max).toBe(0.5);
    expect(DISEASE_TARGETS_NUMERIC_PARAMS).toEqual(["min_score"]);
  });
});
