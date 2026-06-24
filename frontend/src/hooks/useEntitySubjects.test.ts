import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../tests/handlers";
import { deriveSubjects, useEntitySubjects } from "./useEntitySubjects";
import type { AnalysisRead, DiseaseRead, PlantRead } from "../api/types.gen";

const BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PLANTS: PlantRead[] = [
  {
    plant_id: "p1",
    canonical_key: "gbif:1",
    canonical_scientific_name: "Curcuma longa",
    family_name: null,
  },
  {
    plant_id: "p2",
    canonical_key: "gbif:2",
    canonical_scientific_name: "Zingiber officinale",
    family_name: null,
  },
];

const DISEASES: DiseaseRead[] = [
  {
    disease_id: "d1",
    canonical_key: "doid:1",
    disease_name: "Type 2 Diabetes",
    ontology_id: null,
    ontology_source: null,
    source_url: null,
    retrieved_at: null,
  },
];

// ---------------------------------------------------------------------------
// Tests — selection mode
// ---------------------------------------------------------------------------

describe("deriveSubjects — selection mode", () => {
  it("returns catalog name for plant in selection mode", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("Curcuma longa");
  });

  it("joins multiple plant names with a comma", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1", "p2"] },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("Curcuma longa, Zingiber officinale");
  });

  it("returns catalog name for disease in selection mode", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.disease).toBe("Type 2 Diabetes");
  });

  it("falls back to disease_id when disease not in catalog", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      "doid:unknown",
      PLANTS,
      DISEASES,
    );
    expect(result.disease).toBe("doid:unknown");
  });
});

// ---------------------------------------------------------------------------
// Tests — manual mode
// ---------------------------------------------------------------------------

describe("deriveSubjects — manual mode", () => {
  it("returns the plant label in manual_compounds mode", () => {
    const result = deriveSubjects(
      {
        input_modes: { plant: "manual_compounds", disease: "selection" },
        labels: { plant: "My Herb" },
        plant_ids: [],
      },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("My Herb");
  });

  it("returns the plant label in manual_targets mode", () => {
    const result = deriveSubjects(
      {
        input_modes: { plant: "manual_targets", disease: "selection" },
        labels: { plant: "Custom Plant" },
        plant_ids: [],
      },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("Custom Plant");
  });

  it("returns the disease label in manual_disease_targets mode", () => {
    const result = deriveSubjects(
      {
        input_modes: { plant: "selection", disease: "manual_disease_targets" },
        labels: { disease: "My Disease" },
        plant_ids: ["p1"],
      },
      null,
      PLANTS,
      DISEASES,
    );
    expect(result.disease).toBe("My Disease");
  });

  it("returns 'N/A' when manual mode has no label", () => {
    const result = deriveSubjects(
      {
        input_modes: { plant: "manual_compounds", disease: "manual_disease_targets" },
        plant_ids: [],
      },
      null,
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("N/A");
    expect(result.disease).toBe("N/A");
  });
});

// ---------------------------------------------------------------------------
// Tests — missing / empty inputs
// ---------------------------------------------------------------------------

describe("deriveSubjects — missing or empty inputs", () => {
  it("returns '—' for both when parameters is undefined", () => {
    const result = deriveSubjects(undefined, null, PLANTS, DISEASES);
    expect(result.plant).toBe("—");
    expect(result.disease).toBe("—");
  });

  it("returns '—' for plant when plant_ids is empty in selection mode", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: [] },
      "d1",
      PLANTS,
      DISEASES,
    );
    expect(result.plant).toBe("—");
  });

  it("returns '—' for disease when disease_id is null in selection mode", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      null,
      PLANTS,
      DISEASES,
    );
    expect(result.disease).toBe("—");
  });

  it("treats missing input_modes as selection mode (legacy runs)", () => {
    // Legacy runs have no input_modes — treated as selection
    const result = deriveSubjects({ plant_ids: ["p1"] }, "d1", PLANTS, DISEASES);
    expect(result.plant).toBe("Curcuma longa");
    expect(result.disease).toBe("Type 2 Diabetes");
  });

  it("returns plant_id as fallback when plant not found in catalog", () => {
    const result = deriveSubjects({ plant_ids: ["p-unknown"] }, "d1", PLANTS, DISEASES);
    expect(result.plant).toBe("p-unknown");
  });

  it("handles empty catalogs gracefully", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      "d1",
      [],
      [],
    );
    // plant_id and disease_id used as fallback
    expect(result.plant).toBe("p1");
    expect(result.disease).toBe("d1");
  });

  it("does not expose raw ids while selection catalogs are still loading", () => {
    const result = deriveSubjects(
      { input_modes: { plant: "selection", disease: "selection" }, plant_ids: ["p1"] },
      "d1",
      undefined,
      undefined,
    );
    expect(result.plant).toBe("—");
    expect(result.disease).toBe("—");
  });
});

// ---------------------------------------------------------------------------
// Tests — the hook fetches a complete catalog (regression: plant UUID leak)
// ---------------------------------------------------------------------------

describe("useEntitySubjects — full catalog resolution", () => {
  function wrapper() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, children);
  }

  it("resolves a plant that sorts past the default 50-row page (never leaks the UUID)", async () => {
    // A 100-plant catalog whose target sits at index 99 — beyond any default 50-row page.
    // The handler honours `limit`, so resolution only succeeds if the hook asks for the
    // whole catalog rather than the backend's default of 50.
    const target: PlantRead = {
      plant_id: "p-deep",
      canonical_key: "gbif:deep",
      canonical_scientific_name: "Curcuma longa",
      family_name: null,
    };
    server.use(
      http.get(`${BASE}/plants`, ({ request }) => {
        const limit = Number(new URL(request.url).searchParams.get("limit") ?? "50");
        const all: PlantRead[] = [
          ...Array.from({ length: 99 }, (_, i) => ({
            plant_id: `p${i}`,
            canonical_key: `gbif:${i}`,
            canonical_scientific_name: `Plant ${i}`,
            family_name: null,
          })),
          target,
        ];
        return HttpResponse.json(all.slice(0, limit));
      }),
    );

    const run = {
      analysis_id: "a1",
      disease_id: null,
      parameters: {
        input_modes: { plant: "selection", disease: "selection" },
        plant_ids: ["p-deep"],
      },
    } as unknown as AnalysisRead;

    const { result } = renderHook(() => useEntitySubjects(run), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.plant).toBe("Curcuma longa"));
  });
});
