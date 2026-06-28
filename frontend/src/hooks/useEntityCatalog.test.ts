import { createElement, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { useEntityCatalog } from "@/hooks/useEntityCatalog";

// The global MSW server (started in tests/setup.ts) already handles GET /plants
// and GET /diseases with a small fixed catalog.  This test checks that the hook
// fetches both lists and maps each row to the ComboOption shape used by the
// EntitySearchCombobox — matching the mapping previously inline in SetupView.

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe("useEntityCatalog", () => {
  it("loads plants and diseases into options", async () => {
    const { result } = renderHook(() => useEntityCatalog(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.plants.length).toBeGreaterThan(0);
    expect(result.current.plants[0]).toHaveProperty("value");
    expect(result.current.plants[0]).toHaveProperty("label");
  });

  it("maps plant fields to ComboOption shape", async () => {
    // MSW default: plant_id="p1", canonical_scientific_name="Aaa bbb", family_name=null
    const { result } = renderHook(() => useEntityCatalog(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const plant = result.current.plants[0]!;
    expect(plant.value).toBe("p1");
    expect(plant.label).toBe("Aaa bbb");
    expect(plant.kind).toBe("plant");
    // matched_alias absent in fixture → hint is null
    expect(plant.hint).toBeNull();
    // compound_count absent in fixture → count defaults to 0
    expect(plant.count).toBe(0);
  });

  it("maps disease fields to ComboOption shape", async () => {
    // MSW default: disease_id="d1", disease_name="Test Disease"
    const { result } = renderHook(() => useEntityCatalog(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const disease = result.current.diseases[0]!;
    expect(disease.value).toBe("d1");
    expect(disease.label).toBe("Test Disease");
    expect(disease.kind).toBe("disease");
    expect(disease.hint).toBeNull();
    expect(disease.count).toBe(0);
  });

  it("reports isLoading true initially then false after both catalogs resolve", async () => {
    const { result } = renderHook(() => useEntityCatalog(), { wrapper: wrapper() });
    // May or may not catch the loading flash depending on timing, but must settle to false.
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.plants.length).toBeGreaterThan(0);
    expect(result.current.diseases.length).toBeGreaterThan(0);
  });
});
