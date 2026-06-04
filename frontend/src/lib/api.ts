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
} from '@/types/api'

export const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Extract a human-readable message from a FastAPI error response body. */
function extractErrorMessage(status: number, body: unknown): string {
  // 502/503: always override with a friendly retry message regardless of body.
  if (status === 502 || status === 503) {
    return 'The service is temporarily unavailable — please try again.'
  }

  if (body !== null && typeof body === 'object') {
    const detail = (body as Record<string, unknown>).detail
    if (Array.isArray(detail)) {
      // Pydantic 422 validation array: [{msg, loc, type}, ...]
      return detail
        .map((e) =>
          e !== null && typeof e === 'object' && 'msg' in e
            ? String((e as Record<string, unknown>).msg)
            : JSON.stringify(e),
        )
        .join('; ')
    }
    if (typeof detail === 'string' && detail) {
      return detail
    }
  }

  // Generic fallback: include the status code so it's still identifiable.
  return `Request failed with status ${status}.`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      ...init,
    })
  } catch {
    throw new ApiError(0, "Couldn't reach the server — check your connection and try again.")
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    let parsed: unknown = null
    try {
      parsed = text ? JSON.parse(text) : null
    } catch {
      // not JSON — parsed stays null
    }
    throw new ApiError(res.status, extractErrorMessage(res.status, parsed))
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
    request(`/analyses/${encodeURIComponent(id)}`),

  getAnalysisStatus: (id: string): Promise<AnalysisStatusResponse> =>
    request(`/analyses/${encodeURIComponent(id)}/status`),

  approveStage: (id: string, body?: ApproveRequest): Promise<void> =>
    request(`/analyses/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),

  rejectStage: (id: string): Promise<void> =>
    request(`/analyses/${encodeURIComponent(id)}/reject`, { method: 'POST' }),

  deleteAnalysis: (id: string): Promise<void> =>
    request(`/analyses/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  exportStage: (id: string, stage: number, format: 'csv' | 'json'): Promise<Response> =>
    fetch(`${BASE_URL}/analyses/${encodeURIComponent(id)}/export/${stage}?format=${format}`),

  importTargets: (id: string, body: ImportTargetsRequest): Promise<ImportTargetsResponse> =>
    request(`/analyses/${encodeURIComponent(id)}/import-targets`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  resetFromStage: (id: string, stage: number, body?: ResetFromRequest): Promise<AnalysisStatusResponse> =>
    request(`/analyses/${encodeURIComponent(id)}/reset-from/${stage}`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),

  async addUserTarget(analysisId: string, body: AddUserTargetRequest): Promise<AddUserTargetResponse> {
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/targets/user`, {
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
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/targets/${encodeURIComponent(geneSymbol)}`, {
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
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/disease-targets/user`, {
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
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/disease-targets/${encodeURIComponent(geneSymbol)}`, {
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
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/user-compounds`, {
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
    const res = await fetch(`${BASE_URL}/analyses/${encodeURIComponent(analysisId)}/user-compounds/${encodeURIComponent(compoundId)}`, {
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

}
