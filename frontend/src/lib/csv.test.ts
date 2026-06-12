import { describe, it, expect } from "vitest";
import { escapeCsv, buildCsv } from "./csv";

describe("escapeCsv", () => {
  it("passes through plain values", () => {
    expect(escapeCsv("EGFR")).toBe("EGFR");
    expect(escapeCsv(null)).toBe("");
    expect(escapeCsv(0.5)).toBe("0.5");
  });
  it("quotes and doubles quotes when the value has a comma, quote, or newline", () => {
    expect(escapeCsv("a,b")).toBe('"a,b"');
    expect(escapeCsv('he said "hi"')).toBe('"he said ""hi"""');
    expect(escapeCsv("line1\nline2")).toBe('"line1\nline2"');
  });
});

describe("buildCsv", () => {
  it("joins the header and escaped rows", () => {
    const csv = buildCsv("gene,score", [
      ["EGFR", 0.9],
      ["TP53, family", null],
    ]);
    expect(csv).toBe('gene,score\nEGFR,0.9\n"TP53, family",');
  });
});
