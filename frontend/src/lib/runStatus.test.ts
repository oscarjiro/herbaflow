import { describe, it, expect } from "vitest";
import { runningStage, isRunBusy } from "./runStatus";

describe("runningStage", () => {
  it("extracts the stage number from a stage_N_running status", () => {
    expect(runningStage("stage_1_running")).toBe(1);
    expect(runningStage("stage_8_running")).toBe(8);
  });

  it("returns null for non-running statuses", () => {
    expect(runningStage("stage_3_awaiting_approval")).toBeNull();
    expect(runningStage("complete")).toBeNull();
    expect(runningStage("failed")).toBeNull();
    expect(runningStage("created")).toBeNull();
  });

  it("returns null for nullish input", () => {
    expect(runningStage(null)).toBeNull();
    expect(runningStage(undefined)).toBeNull();
  });
});

describe("isRunBusy", () => {
  it("is true while any stage is running", () => {
    expect(isRunBusy("stage_1_running")).toBe(true);
    expect(isRunBusy("stage_5_running")).toBe(true);
  });

  it("is false when the run is not computing a stage", () => {
    expect(isRunBusy("stage_3_awaiting_approval")).toBe(false);
    expect(isRunBusy("complete")).toBe(false);
    expect(isRunBusy("failed")).toBe(false);
    expect(isRunBusy(null)).toBe(false);
    expect(isRunBusy(undefined)).toBe(false);
  });
});
