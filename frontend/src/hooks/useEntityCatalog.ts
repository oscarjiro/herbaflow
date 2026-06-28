import { useQuery } from "@tanstack/react-query";
import { listDiseases, listPlants } from "@/api/sdk.gen";
import type { ComboOption } from "@/components/EntitySearchCombobox";

// Fetches the full catalog in one request. The endpoints have no upper cap on
// `limit`, so 1000 is large enough to cover the full catalog (478 plants / ~10
// diseases at time of writing) without pagination.
const CATALOG_LIMIT = 1000;

export function useEntityCatalog(): {
  plants: ComboOption[];
  diseases: ComboOption[];
  isLoading: boolean;
} {
  const plantsQ = useQuery({
    queryKey: ["entity-catalog", "plants"],
    staleTime: Infinity,
    queryFn: async () => {
      const { data } = await listPlants({ query: { limit: CATALOG_LIMIT } });
      return (data ?? []).map(
        (p): ComboOption => ({
          value: p.plant_id,
          label: p.canonical_scientific_name ?? p.plant_id,
          hint: p.matched_alias ?? null,
          familyName: p.family_name ?? null,
          count: p.compound_count ?? 0,
          kind: "plant" as const,
        }),
      );
    },
  });

  const diseasesQ = useQuery({
    queryKey: ["entity-catalog", "diseases"],
    staleTime: Infinity,
    queryFn: async () => {
      const { data } = await listDiseases({ query: { limit: CATALOG_LIMIT } });
      return (data ?? []).map(
        (d): ComboOption => ({
          value: d.disease_id,
          label: d.disease_name ?? d.disease_id,
          hint: d.matched_alias ?? null,
          count: d.target_count ?? 0,
          kind: "disease" as const,
        }),
      );
    },
  });

  return {
    plants: plantsQ.data ?? [],
    diseases: diseasesQ.data ?? [],
    isLoading: plantsQ.isLoading || diseasesQ.isLoading,
  };
}
