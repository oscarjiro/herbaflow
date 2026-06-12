import type { AnalysisRead } from "../../api/types.gen";
import { useEntitySubjects } from "../../hooks/useEntitySubjects";

/**
 * Small per-stage context line showing the entity a stage operates on — the plant for the
 * plant-side stages (1/2/3), the disease for the disease stage (4). Reuses the one shared subject
 * derivation.
 */
export function StageEntityContext({
  data,
  side,
}: {
  data: AnalysisRead;
  side: "plant" | "disease";
}) {
  const subjects = useEntitySubjects(data);
  const label = side === "plant" ? "Plant" : "Disease";
  const value = side === "plant" ? subjects.plant : subjects.disease;
  return (
    <p className="stage-context hf-muted">
      {label}: {value}
    </p>
  );
}
