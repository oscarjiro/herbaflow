import { API_BASE_URL } from "./api";

/** Absolute URL of a completed run's downloadable results bundle (zip). */
export function exportBundleUrl(analysisId: string): string {
  return `${API_BASE_URL}/analyses/${analysisId}/export`;
}
