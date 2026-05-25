import type {
  PlantResponse,
  DiseaseResponse,
  CreateAnalysisRequest,
  AnalysisRunResponse,
  AnalysisStatusResponse,
  ImportTargetsRequest,
  ImportTargetsResponse,
  ResetFromRequest,
  ApproveRequest,
  AddUserTargetRequest,
  AddUserTargetResponse,
  InjectCompoundsResponse,
  InjectTargetsResponse,
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

  approveStage: (id: string, body?: ApproveRequest): Promise<void> =>
    request(`/analyses/${id}/approve`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),

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

  async addUserTarget(analysisId: string, body: AddUserTargetRequest): Promise<AddUserTargetResponse> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/targets/user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to add target')
    }
    return res.json()
  },

  async removeUserTarget(analysisId: string, geneSymbol: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/targets/${encodeURIComponent(geneSymbol)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to remove target')
    }
  },

  async addUserDiseaseTarget(analysisId: string, body: AddUserTargetRequest): Promise<AddUserTargetResponse> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/disease-targets/user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to add disease target')
    }
    return res.json()
  },

  async removeUserDiseaseTarget(analysisId: string, geneSymbol: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/disease-targets/${encodeURIComponent(geneSymbol)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Failed to remove disease target')
    }
  },

  // T4.3: Inject manually-provided SMILES/InChI strings as stage 1+2 results
  injectCompounds(analysisId: string, compounds: string[]): Promise<InjectCompoundsResponse> {
    return request(`/analyses/${analysisId}/inject-compounds`, {
      method: 'POST',
      body: JSON.stringify({ compounds }),
    })
  },

  // T4.4: Inject manually-provided gene symbols or UniProt accessions as stage 3 results
  injectTargets(analysisId: string, targets: string[]): Promise<InjectTargetsResponse> {
    return request(`/analyses/${analysisId}/inject-targets`, {
      method: 'POST',
      body: JSON.stringify({ targets }),
    })
  },
}
