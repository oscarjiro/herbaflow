import { API_BASE_URL } from "./api";

const base = (id: string) => `${API_BASE_URL}/analyses/${id}/export`;

export const exportReportUrl = (id: string) => `${base(id)}/report.md`;
export const exportNetworkBundleUrl = (id: string) => `${base(id)}/network.zip`;
export const exportStagesBundleUrl = (id: string) => `${base(id)}/stages.zip`;
export const exportAllResultsUrl = (id: string) => `${base(id)}/all-results.zip`;
export const exportArtifactUrl = (id: string, filename: string) => `${base(id)}/${filename}`;

// The stored STRING PPI image, served the moment Stage 6 finishes (not gated on a complete run,
// unlike the /export/ artifacts above). Backed by GET /analyses/{id}/stage6-image.png.
export const stage6ImageUrl = (id: string) => `${API_BASE_URL}/analyses/${id}/stage6-image.png`;
