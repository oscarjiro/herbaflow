import { describe, expect, it, test } from "vitest";
import { formatSig, formatCount } from "./format";
import { formatRelative } from "./format";

describe("formatSig", () => {
  it("rounds to 4 significant figures and trims trailing zeros", () => {
    expect(formatSig(0.17647058823)).toBe("0.1765");
    expect(formatSig(12.34567)).toBe("12.35");
    expect(formatSig(0.30000000004)).toBe("0.3");
  });
  it("renders an em dash for null/undefined/NaN", () => {
    expect(formatSig(null)).toBe("—");
    expect(formatSig(undefined)).toBe("—");
    expect(formatSig(Number.NaN)).toBe("—");
  });
  it("keeps zero as 0", () => {
    expect(formatSig(0)).toBe("0");
  });
});

describe("formatCount", () => {
  it("groups thousands with separators", () => {
    expect(formatCount(1240567)).toBe("1,240,567");
    expect(formatCount(2000)).toBe("2,000");
    expect(formatCount(12345)).toBe("12,345");
  });
  it("is a no-op below 1,000", () => {
    expect(formatCount(999)).toBe("999");
    expect(formatCount(42)).toBe("42");
    expect(formatCount(0)).toBe("0");
  });
  it("renders an em dash for null/undefined/NaN", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(undefined)).toBe("—");
    expect(formatCount(Number.NaN)).toBe("—");
  });
});

test("formatRelative renders a short relative string", () => {
  const twoMinAgo = new Date(Date.now() - 2 * 60 * 1000).toISOString();
  expect(formatRelative(twoMinAgo)).toMatch(/2 min/i);
});
