import type { AnalysisRead } from "../../api/types.gen";
import { useEntitySubjects } from "../../hooks/useEntitySubjects";
import { Eyebrow } from "@/components/ui/editorial";

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
  // Inline flow (not flex) so a long entity value wraps like a paragraph —
  // left-aligned to the container edge — instead of hang-indenting under the
  // value column, which looked broken at the 320px floor.
  return (
    <p className="text-sm [color:var(--hf-fg-3)]">
      <Eyebrow>{label}:</Eyebrow> <span>{value}</span>
    </p>
  );
}
