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

  it('treats a stale "null" string as no active run and self-clears it', () => {
    // An older build could persist localStorage.setItem(KEY, null), which the
    // platform coerces to the string "null" and would route to /analysis/null.
    localStorage.setItem("hf-active-run", "null");
    expect(getActiveRunId()).toBeNull();
    expect(localStorage.getItem("hf-active-run")).toBeNull();
  });

  it('treats a stale "undefined" string as no active run', () => {
    localStorage.setItem("hf-active-run", "undefined");
    expect(getActiveRunId()).toBeNull();
  });

  it("never persists a nullish or sentinel id", () => {
    setActiveRunId(null as unknown as string);
    setActiveRunId("null");
    setActiveRunId("");
    expect(getActiveRunId()).toBeNull();
  });
});
