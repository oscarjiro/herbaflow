import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SITE_DESCRIPTION, SITE_NAME, pageTitle, runPageTitle, useDocumentTitle } from "./pageMeta";

describe("pageTitle", () => {
  it("suffixes the site name with a dash separator", () => {
    expect(pageTitle(["About"])).toBe("About - Herbaflow");
  });
  it("returns bare brand for no segments", () => {
    expect(pageTitle([])).toBe("Herbaflow");
  });
  it("drops empty/whitespace segments", () => {
    expect(pageTitle(["", "  ", "New analysis"])).toBe("New analysis - Herbaflow");
  });
});

describe("runPageTitle", () => {
  it("composes subject × subject - Stage N - Herbaflow", () => {
    expect(runPageTitle({ plant: "Curcuma longa", disease: "Type 2 Diabetes" }, 3)).toBe(
      "Curcuma longa × Type 2 Diabetes - Stage 3 - Herbaflow",
    );
  });
  it("falls back to Analysis when a side is unresolved", () => {
    expect(runPageTitle({ plant: "—", disease: "Type 2 Diabetes" }, 3)).toBe(
      "Analysis - Stage 3 - Herbaflow",
    );
  });
  it("omits the stage segment when current stage is null", () => {
    expect(runPageTitle({ plant: "—", disease: "—" }, null)).toBe("Analysis - Herbaflow");
  });
});

describe("constants", () => {
  it("exposes the brand + description", () => {
    expect(SITE_NAME).toBe("Herbaflow");
    expect(SITE_DESCRIPTION).toContain("network pharmacology platform");
    expect(SITE_DESCRIPTION).not.toContain("—"); // no em dash in display copy
  });
});

describe("useDocumentTitle", () => {
  it("sets document.title on mount and on change", () => {
    const { rerender } = renderHook(({ t }) => useDocumentTitle(t), {
      initialProps: { t: "About - Herbaflow" },
    });
    expect(document.title).toBe("About - Herbaflow");
    rerender({ t: "New analysis - Herbaflow" });
    expect(document.title).toBe("New analysis - Herbaflow");
  });
});
