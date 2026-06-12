import { useQuery } from "@tanstack/react-query";
import { listDiseasesOptions, listPlantsOptions } from "../api/@tanstack/react-query.gen";
import type { AnalysisRead } from "../api/types.gen";

/**
 * The single home for resolving a run's plant + disease display strings: selection (or legacy
 * no-input_modes) -> catalog names; manual modes -> the optional free-text label, else "N/A". Used by
 * the run header and every per-stage context line so the derivation lives once. The two catalog
 * queries are deduped by TanStack Query with SetupView/RunView.
 */
export function useEntitySubjects(data: AnalysisRead | undefined): {
  plant: string;
  disease: string;
} {
  const { data: plantsData } = useQuery(listPlantsOptions());
  const { data: diseasesData } = useQuery(listDiseasesOptions());

  if (!data) return { plant: "—", disease: "—" };

  const params = data.parameters as Record<string, unknown> | undefined;
  const inputModes = params?.input_modes as { plant?: string; disease?: string } | undefined;
  const labels = params?.labels as { plant?: string; disease?: string } | undefined;
  const plantIds = params?.plant_ids as string[] | undefined;

  const plant: string = (() => {
    if (!inputModes || inputModes.plant === "selection") {
      if (!plantIds || plantIds.length === 0) return "—";
      const byId = new Map((plantsData ?? []).map((p) => [p.plant_id, p]));
      const names = plantIds.map(
        (id) => byId.get(id)?.canonical_scientific_name ?? byId.get(id)?.plant_id ?? id,
      );
      return names.join(", ") || "—";
    }
    return labels?.plant ?? "N/A";
  })();

  const disease: string = (() => {
    if (!inputModes || inputModes.disease === "selection") {
      if (!data.disease_id) return "—";
      const byId = new Map((diseasesData ?? []).map((d) => [d.disease_id, d]));
      return byId.get(data.disease_id)?.disease_name ?? data.disease_id;
    }
    return labels?.disease ?? "N/A";
  })();

  return { plant, disease };
}
