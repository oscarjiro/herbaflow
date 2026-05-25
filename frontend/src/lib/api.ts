import type {
  PlantResponse,
  DiseaseResponse,
  CreateAnalysisRequest,
  AnalysisRunResponse,
  AnalysisStatusResponse,
  ImportTargetsRequest,
  ImportTargetsResponse,
  ResetFromRequest,
} from '@/types/api'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getPlants: (): Promise<PlantResponse[]> =>
    request('/plants'),

  getDiseases: (): Promise<DiseaseResponse[]> =>
    request('/diseases'),

  createAnalysis: (body: CreateAnalysisRequest): Promise<{ analysis_id: string }> =>
    request('/analyses', { method: 'POST', body: JSON.stringify(body) }),

  getAnalysis: (id: string): Promise<AnalysisRunResponse> =>
    request(`/analyses/${id}`),

  getAnalysisStatus: (id: string): Promise<AnalysisStatusResponse> =>
    request(`/analyses/${id}/status`),

  approveStage: (id: string): Promise<void> =>
    request(`/analyses/${id}/approve`, { method: 'POST' }),

  rejectStage: (id: string): Promise<void> =>
    request(`/analyses/${id}/reject`, { method: 'POST' }),

  deleteAnalysis: (id: string): Promise<void> =>
    request(`/analyses/${id}`, { method: 'DELETE' }),

  exportStage: (id: string, stage: number, format: 'csv' | 'json'): Promise<Response> =>
    fetch(`${BASE_URL}/analyses/${id}/export/${stage}?format=${format}`),

  importTargets: (id: string, body: ImportTargetsRequest): Promise<ImportTargetsResponse> =>
    request(`/analyses/${id}/import-targets`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  resetFromStage: (id: string, stage: number, body?: ResetFromRequest): Promise<AnalysisStatusResponse> =>
    request(`/analyses/${id}/reset-from/${stage}`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
}
