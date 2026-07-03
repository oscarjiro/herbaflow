import { useQuery } from "@tanstack/react-query";
import { listDiseasesOptions, listPlantsOptions } from "../api/@tanstack/react-query.gen";
import type { AnalysisRead, DiseaseRead, PlantRead } from "../api/types.gen";

/**
 * Pure derivation core — no hooks, no side-effects.
 * Takes the raw parameters bag, disease_id, and the two catalog arrays and returns
 * the plant + disease display strings.
 *
 * Selection mode (or legacy no-input_modes) → catalog name.
 * Manual mode → optional free-text label, else "N/A".
 * Missing / empty → "—".
 */
export function deriveSubjects(
  parameters: Record<string, unknown> | undefined,
  diseaseId: string | null | undefined,
  plants: PlantRead[] | undefined,
  diseases: DiseaseRead[] | undefined,
): { plant: string; disease: string } {
  const inputModes = parameters?.input_modes as { plant?: string; disease?: string } | undefined;
  const labels = parameters?.labels as { plant?: string; disease?: string } | undefined;
  const plantIds = parameters?.plant_ids as string[] | undefined;

  const plant: string = (() => {
    if (!inputModes || inputModes.plant === "selection") {
      // New runs store the resolved catalog name(s) at create time — read them straight
      // off the run. The catalog lookup below is only a fallback for legacy runs that
      // predate create-time label storage.
      if (labels?.plant) return labels.plant;
      if (!plantIds || plantIds.length === 0) return "—";
      if (plants === undefined) return "—";
      const byId = new Map((plants ?? []).map((p) => [p.plant_id, p]));
      const names = plantIds.map(
        (id) => byId.get(id)?.canonical_scientific_name ?? byId.get(id)?.plant_id ?? id,
      );
      return names.join(", ") || "—";
    }
    return labels?.plant ?? "N/A";
  })();

  const disease: string = (() => {
    if (!inputModes || inputModes.disease === "selection") {
      if (labels?.disease) return labels.disease;
      if (!diseaseId) return "—";
      if (diseases === undefined) return "—";
      const byId = new Map((diseases ?? []).map((d) => [d.disease_id, d]));
      return byId.get(diseaseId)?.disease_name ?? diseaseId;
    }
    return labels?.disease ?? "N/A";
  })();

  return { plant, disease };
}

// Pull the entire catalog so any selected id resolves to a name. The backend defaults to 50
// rows; with 478 plants that silently dropped most names to their raw UUID. There is no
// get-by-id endpoint, so we fetch the full list once (cached + deduped by TanStack Query).
const CATALOG_LIMIT = 1000;

/**
 * The single home for resolving a run's plant + disease display strings. Used by the run header
 * and every per-stage context line so the derivation lives once. The two catalog queries are
 * deduped by TanStack Query across the app.
 */
export function useEntitySubjects(data: AnalysisRead | undefined): {
  plant: string;
  disease: string;
} {
  const params = data?.parameters as Record<string, unknown> | undefined;
  const inputModes = params?.input_modes as { plant?: string; disease?: string } | undefined;
  const labels = params?.labels as { plant?: string; disease?: string } | undefined;

  // Only fetch the catalog for a selection-mode side whose display name wasn't stored on the
  // run (legacy runs predating create-time label storage). New runs read straight off
  // `labels`, so the run header/context never waits on a second catalog round-trip.
  const needPlants = (!inputModes || inputModes.plant === "selection") && !labels?.plant;
  const needDiseases = (!inputModes || inputModes.disease === "selection") && !labels?.disease;

  const { data: plantsData } = useQuery({
    ...listPlantsOptions({ query: { limit: CATALOG_LIMIT } }),
    enabled: needPlants,
  });
  const { data: diseasesData } = useQuery({
    ...listDiseasesOptions({ query: { limit: CATALOG_LIMIT } }),
    enabled: needDiseases,
  });

  if (!data) return { plant: "—", disease: "—" };

  return deriveSubjects(params, data.disease_id, plantsData, diseasesData);
}
