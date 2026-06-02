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
  AddUserCompoundRequest,
  AddUserCompoundResponse,
  InjectCompoundsRequest,
  InjectCompoundsResponse,
  InjectTargetsRequest,
  InjectTargetsResponse,
} from '@/types/api'

export const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  // Tolerate empty bodies (e.g. 204 No Content): calling res.json() on an
  // empty body throws a SyntaxError, so return undefined for void responses.
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
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
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to add target')
      throw new Error(detail)
    }
    return res.json()
  },

  async removeUserTarget(analysisId: string, geneSymbol: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/targets/${encodeURIComponent(geneSymbol)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to remove target')
      throw new Error(detail)
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
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to add disease target')
      throw new Error(detail)
    }
    return res.json()
  },

  async removeUserDiseaseTarget(analysisId: string, geneSymbol: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/disease-targets/${encodeURIComponent(geneSymbol)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to remove disease target')
      throw new Error(detail)
    }
  },

  async addUserCompound(analysisId: string, body: AddUserCompoundRequest): Promise<AddUserCompoundResponse> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/user-compounds`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to add compound')
      throw new Error(detail)
    }
    return res.json()
  },

  async removeUserCompound(analysisId: string, compoundId: string): Promise<{ removed: string }> {
    const res = await fetch(`${BASE_URL}/analyses/${analysisId}/user-compounds/${encodeURIComponent(compoundId)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((e: { msg: string }) => e.msg).join('; ')
        : (err?.detail ?? 'Failed to remove compound')
      throw new Error(detail)
    }
    return res.json()
  },

  // Inject manually-provided SMILES/InChI strings as stage 1+2 results
  injectCompounds(analysisId: string, compounds: string[]): Promise<InjectCompoundsResponse> {
    const body: InjectCompoundsRequest = { compounds }
    return request(`/analyses/${analysisId}/inject-compounds`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  // Inject manually-provided gene symbols or UniProt accessions as stage 3 results
  injectTargets(analysisId: string, targets: string[]): Promise<InjectTargetsResponse> {
    const body: InjectTargetsRequest = { targets }
    return request(`/analyses/${analysisId}/inject-targets`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
}
