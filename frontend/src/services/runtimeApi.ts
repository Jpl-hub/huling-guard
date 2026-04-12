import type {
  ArchiveListResponse,
  ArchiveRecord,
  ArchiveSummaryResponse,
  DemoSessionResponse,
  DemoVideosResponse,
  HealthResponse,
  Incident,
  MetaResponse,
  RuntimeStateResponse,
  SessionReport,
  SummaryResponse,
  SystemProfileResponse,
  TimelineResponse,
  LiveSourceResponse,
  LiveIngestStatusResponse,
  UploadVideoResponse,
} from '../types/runtime'

const baseUrl = (import.meta.env.VITE_RUNTIME_BASE_URL ?? '').replace(/\/$/, '')

function buildUrl(path: string): string {
  return baseUrl ? `${baseUrl}${path}` : path
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), init)
  if (!response.ok) {
    let detail = `${response.status}`
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string') {
        detail = payload.detail
      }
    } catch {
      const text = await response.text()
      if (text.trim()) {
        detail = text.trim()
      }
    }
    throw new Error(detail)
  }
  if (response.status === 204) {
    return {} as T
  }
  return (await response.json()) as T
}

export const runtimeApi = {
  mediaUrl: (path: string) => buildUrl(path),
  health: () => request<HealthResponse>('/health'),
  meta: () => request<MetaResponse>('/meta'),
  state: () => request<RuntimeStateResponse>('/state'),
  summary: () => request<SummaryResponse>('/summary'),
  timeline: (limit = 120) => request<TimelineResponse>(`/timeline?limit=${limit}`),
  incidents: (limit = 10) => request<{ count: number; items: Incident[] }>(`/incidents?limit=${limit}`),
  systemProfile: () => request<SystemProfileResponse>('/system-profile'),
  sessionReport: () => request<SessionReport>('/session-report'),
  liveSource: () => request<LiveSourceResponse>('/live-source'),
  liveIngestStatus: () => request<LiveIngestStatusResponse>('/live-ingest'),
  startLiveIngest: (payload: { source: string; sourceLabel?: string }) =>
    request<LiveIngestStatusResponse>('/live-ingest/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: payload.source,
        source_label: payload.sourceLabel,
      }),
    }),
  stopLiveIngest: () => request<LiveIngestStatusResponse>('/live-ingest/stop', { method: 'POST' }),
  demoVideos: () => request<DemoVideosResponse>('/demo-videos'),
  demoSession: (filename: string) =>
    request<DemoSessionResponse>(`/demo-sessions/${encodeURIComponent(filename)}`),
  uploadVideo: async (file: File) => {
    const body = new FormData()
    body.set('video', file)
    return request<UploadVideoResponse>('/uploaded-videos', {
      method: 'POST',
      body,
    })
  },
  deleteDemoVideo: (filename: string) =>
    request<{ status: string; removed: string[] }>(`/demo-videos/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    }),

  archives: (params: { limit?: number; dominantState?: string; incidentsOnly?: boolean }) => {
    const search = new URLSearchParams()
    const limit = Math.min(Math.max(Number(params.limit ?? 16), 1), 500)
    search.set('limit', String(limit))
    if (params.dominantState) {
      search.set('dominant_state', params.dominantState)
    }
    if (params.incidentsOnly) {
      search.set('incidents_only', 'true')
    }
    return request<ArchiveListResponse>(`/archives?${search.toString()}`)
  },
  archiveSummary: () => request<ArchiveSummaryResponse>('/archives/summary'),
  archiveById: (sessionId: string) => request<SessionReport>(`/archives/${encodeURIComponent(sessionId)}`),
  archiveSession: (payload?: { demoFilename?: string }) =>
    request<{ status: string }>('/archive-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ demo_filename: payload?.demoFilename ?? null }),
    }),
  deleteArchive: (sessionId: string) =>
    request<{ status: string; record: ArchiveRecord }>(`/archives/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    }),

  reset: () => request<{ status: string }>('/reset', { method: 'POST' }),
}
