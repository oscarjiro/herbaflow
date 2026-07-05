import { useEffect } from "react";

export const SITE_NAME = "Herbaflow";

export const SITE_DESCRIPTION =
  "Herbaflow is a network pharmacology platform for mapping how plants, compounds, diseases, and protein targets connect.";

/** Join non-empty segments with " - " and always suffix the site name. */
export function pageTitle(segments: string[]): string {
  const parts = segments.map((s) => s.trim()).filter(Boolean);
  return [...parts, SITE_NAME].join(" - ");
}

/**
 * Run-page title: "{plant} × {disease} - Stage {N} - Herbaflow".
 * Falls back to "Analysis" as the subject when either side is unresolved
 * ("—" / "N/A" / empty), and omits the stage segment when currentStage is null.
 */
export function runPageTitle(
  subjects: { plant: string; disease: string },
  currentStage: number | null,
): string {
  const usable = (s: string) => Boolean(s) && s !== "—" && s !== "N/A";
  const subject =
    usable(subjects.plant) && usable(subjects.disease)
      ? `${subjects.plant} × ${subjects.disease}`
      : "Analysis";
  const stage = typeof currentStage === "number" ? `Stage ${currentStage}` : "";
  return pageTitle([subject, stage]);
}

/** Set document.title for the current route (tab / bookmarks / Google). */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = title;
    }
  }, [title]);
}
