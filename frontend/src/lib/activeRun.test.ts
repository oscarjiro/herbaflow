import { afterEach, describe, expect, it } from "vitest";
import { clearActiveRunId, getActiveRunId, setActiveRunId } from "./activeRun";

afterEach(() => localStorage.clear());

describe("activeRun storage", () => {
  it("returns null when nothing is stored", () => {
    expect(getActiveRunId()).toBeNull();
  });

  it("round-trips a run id", () => {
    setActiveRunId("abc-123");
    expect(getActiveRunId()).toBe("abc-123");
  });

  it("clears the stored id", () => {
    setActiveRunId("abc-123");
    clearActiveRunId();
    expect(getActiveRunId()).toBeNull();
  });
});
