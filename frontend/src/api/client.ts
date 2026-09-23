import type { ApiErrorBody, CaseSummary, EvalLatest, GraphElements, GraphOntology, Neighbors, RunStatus } from './types'

const API_PREFIX = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    throw new Error(body?.error?.message ?? `Request to ${path} failed with ${response.status}`)
  }
  return (await response.json()) as T
}

export const api = {
  listCases: () => request<CaseSummary[]>('/cases'),
  startRun: (caseId: string) =>
    request<RunStatus>('/runs', { method: 'POST', body: JSON.stringify({ case_id: caseId }) }),
  getRun: (runId: string) => request<RunStatus>(`/runs/${encodeURIComponent(runId)}`),
  getOntology: () => request<GraphOntology>('/graph/ontology'),
  graphElements: (ids: string[]) =>
    request<GraphElements>(`/graph/nodes?ids=${ids.map(encodeURIComponent).join(',')}`),
  neighbors: (id: string) => request<Neighbors>(`/graph/neighbors/${encodeURIComponent(id)}`),
  evalLatest: () => request<EvalLatest>('/eval/latest'),
  eventsUrl: (runId: string) => `${API_PREFIX}/runs/${encodeURIComponent(runId)}/events`,
}
