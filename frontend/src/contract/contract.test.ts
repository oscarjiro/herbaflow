import { describe, expect, it } from "vitest";
import {
  DEFAULT_PLANT_INPUT_MODE,
  DEFAULT_DISEASE_INPUT_MODE,
  PLANT_INPUT_MODES,
  DISEASE_INPUT_MODES,
} from "./index";

describe("input modes", () => {
  it("derives plant modes from the contract", () => {
    expect(PLANT_INPUT_MODES).toEqual(["selection", "manual_compounds", "manual_targets"]);
    expect(DEFAULT_PLANT_INPUT_MODE).toBe("selection");
  });
  it("derives disease modes from the contract", () => {
    expect(DISEASE_INPUT_MODES).toEqual(["selection", "manual_disease_targets"]);
    expect(DEFAULT_DISEASE_INPUT_MODE).toBe("selection");
  });
});
