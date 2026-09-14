import type {
  Adapter,
  ApiErrorBody,
  CaseDetail,
  CasePage,
  DecisionResponse,
  EventPage,
  HealthResponse,
  MetaResponse,
  QueueRunResponse,
  RunCreateRequest,
  RunPage,
  RunStartResponse,
  RunSummary,
  WorkflowGraph,
  MemoryNotePage,
  RunMemoryResponse,
  GraphResponse,
  RunGraphResponse,
  SourceResponse,
  BlobResponse,
} from './types'

const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>
  status: number

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.error.code
    this.details = body.error.details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    if (body?.error) throw new ApiError(response.status, body)
    throw new Error(`Request to ${path} failed with ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function query(params: object): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params) as Array<
    [string, string | number | boolean | undefined]
  >) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export interface ListCasesParams {
  regime?: string
  status?: string
  stage?: string
  claim_family?: string
  q?: string
  limit?: number
  cursor?: number
}

export interface ListRunsParams {
  case_id?: string
  status?: string
  limit?: number
  cursor?: number
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  meta: () => request<MetaResponse>('/meta'),
  workflow: () => request<WorkflowGraph>('/meta/workflow'),

  listCases: (params: ListCasesParams = {}) =>
    request<CasePage>(`/cases${query(params)}`),
  getCase: (caseId: string) => request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`),

  listRuns: (params: ListRunsParams = {}) => request<RunPage>(`/runs${query(params)}`),
  getRun: (runId: string) => request<RunSummary>(`/runs/${encodeURIComponent(runId)}`),
  startRun: (body: RunCreateRequest) =>
    request<RunStartResponse>('/runs', { method: 'POST', body: JSON.stringify(body) }),
  cancelRun: (runId: string) =>
    request<RunSummary>(`/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' }),
  rerunRun: (runId: string) =>
    request<RunStartResponse>(`/runs/${encodeURIComponent(runId)}/rerun`, { method: 'POST' }),
  getRunEvents: (runId: string, afterSeq = 0, limit = 200) =>
    request<EventPage>(
      `/runs/${encodeURIComponent(runId)}/events${query({ after_seq: afterSeq, limit })}`,
    ),
  getRunDecision: (runId: string) =>
    request<DecisionResponse>(`/runs/${encodeURIComponent(runId)}/decision`),
  getRunMemory: (runId: string) => request<RunMemoryResponse>(`/runs/${encodeURIComponent(runId)}/memory`),
  getRunGraph: (runId: string) => request<RunGraphResponse>(`/runs/${encodeURIComponent(runId)}/graph`),
  getBlob: (runId: string, sha256: string) => request<BlobResponse>(`/runs/${encodeURIComponent(runId)}/blobs/${encodeURIComponent(sha256.replace('sha256:', ''))}`),
  listMemoryNotes: (params: { subject?: string; scope?: string; kind?: string; tag?: string; status?: string; min_confidence?: number; as_of?: string; limit?: number } = {}) => request<MemoryNotePage>(`/memory/notes${query(params)}`),
  getCaseGraph: (caseId: string, depth = 2) => request<GraphResponse>(`/graph/cases/${encodeURIComponent(caseId)}${query({ depth })}`),
  getSource: (sourceId: string) => request<SourceResponse>(`/sources/${encodeURIComponent(sourceId)}`),

  startQueueRun: (adapter: Adapter) =>
    request<RunStartResponse>('/queue/runs', {
      method: 'POST',
      body: JSON.stringify({ adapter }),
    }),
  getQueueRun: (runId: string) =>
    request<QueueRunResponse>(`/queue/runs/${encodeURIComponent(runId)}`),

  runStreamUrl: (runId: string, afterSeq = 0) =>
    `${API_PREFIX}/runs/${encodeURIComponent(runId)}/events/stream${query({ after_seq: afterSeq })}`,
}
