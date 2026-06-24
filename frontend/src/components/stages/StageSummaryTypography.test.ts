import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const stageViewFiles = [
  "Stage1View.tsx",
  "Stage2View.tsx",
  "Stage3View.tsx",
  "Stage4View.tsx",
  "Stage5View.tsx",
  "Stage6View.tsx",
  "Stage7View.tsx",
  "Stage8View.tsx",
];

describe("stage summary card typography", () => {
  it.each(stageViewFiles)("%s uses the shared summary-card primitive", (file) => {
    const source = readFileSync(join(__dirname, file), "utf8");

    expect(source).toContain("StageSummaryCard");
    expect(source).not.toMatch(/<span className="hf-num[^"]*text-2xl[^"]*"/);
  });
});
