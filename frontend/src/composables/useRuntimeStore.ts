import { computed, reactive } from 'vue'
import { Message } from '@arco-design/web-vue'

import { runtimeApi } from '../services/runtimeApi'
import type {
  ArchiveListResponse,
  ArchiveSummaryResponse,
  DemoSessionResponse,
  DemoVideoItem,
  DisplayState,
  GuardState,
  HealthResponse,
  Incident,
  MetaResponse,
  QuickAnswer,
  RuntimeStateResponse,
  SessionReport,
  SummaryResponse,
  SystemProfileResponse,
  TimelineResponse,
  ViewMode,
  LiveSourceResponse,
} from '../types/runtime'
import {
  buildDisplayStateFromReport,
  buildDisplayStateFromRuntime,
  buildQuickAnswers,
  buildReportIncidents,
  buildVerdict,
  runtimeChips,
} from '../utils/presenters'

interface RuntimeStoreState {
  loading: boolean
  refreshing: boolean
  errorMessage: string
  health: HealthResponse | null
  meta: MetaResponse | null
  runtimeState: RuntimeStateResponse | null
  runtimeSummary: SummaryResponse | null
  runtimeTimeline: TimelineResponse | null
  runtimeReport: SessionReport | null
  runtimeIncidents: Incident[]
  systemProfile: SystemProfileResponse | null
  liveSource: LiveSourceResponse | null
  demoVideos: DemoVideoItem[]
  selectedDemoFilename: string
  selectedDemoSession: DemoSessionResponse | null
  archives: ArchiveListResponse | null
  archiveSummary: ArchiveSummaryResponse | null
  selectedArchiveId: string
  selectedArchiveReport: SessionReport | null
  archiveFilterState: string
  archiveIncidentsOnly: boolean
  lastUpdatedAt: string
  mode: ViewMode
}

const state = reactive<RuntimeStoreState>({
  loading: true,
  refreshing: false,
  errorMessage: '',
  health: null,
  meta: null,
  runtimeState: null,
  runtimeSummary: null,
  runtimeTimeline: null,
  runtimeReport: null,
  runtimeIncidents: [],
  systemProfile: null,
  liveSource: null,
  demoVideos: [],
  selectedDemoFilename: '',
  selectedDemoSession: null,
  archives: null,
  archiveSummary: null,
  selectedArchiveId: '',
  selectedArchiveReport: null,
  archiveFilterState: '',
  archiveIncidentsOnly: false,
  lastUpdatedAt: '',
  mode: 'care',
})

let pollingTimer: number | null = null

function preferredDemoFilename(items: DemoVideoItem[]): string {
  const preferred = items.find((item) => item.filename.includes('fall'))
  return preferred?.filename ?? items[0]?.filename ?? ''
}

async function refreshArchives(): Promise<void> {
  if (!state.meta?.archive_enabled) {
    state.archives = null
    state.archiveSummary = null
    state.selectedArchiveId = ''
    state.selectedArchiveReport = null
    return
  }

  const [archivesPayload, archiveSummaryPayload] = await Promise.all([
    runtimeApi.archives({
      limit: 16,
      dominantState: state.archiveFilterState || undefined,
      incidentsOnly: state.archiveIncidentsOnly,
    }),
    runtimeApi.archiveSummary(),
  ])

  state.archives = archivesPayload
  state.archiveSummary = archiveSummaryPayload

  const availableIds = new Set(archivesPayload.items.map((item) => item.session_id))
  if (!state.selectedArchiveId || !availableIds.has(state.selectedArchiveId)) {
    state.selectedArchiveId = archivesPayload.items[0]?.session_id ?? ''
  }

  if (state.selectedArchiveId) {
    state.selectedArchiveReport = await runtimeApi.archiveById(state.selectedArchiveId)
  } else {
    state.selectedArchiveReport = null
  }
}

async function refreshDemos(): Promise<void> {
  const payload = await runtimeApi.demoVideos()
  state.demoVideos = payload.items
  if (!state.selectedDemoFilename && payload.items.length) {
    state.selectedDemoFilename = preferredDemoFilename(payload.items)
  }
  if (state.selectedDemoFilename) {
    try {
      state.selectedDemoSession = await runtimeApi.demoSession(state.selectedDemoFilename)
    } catch {
      state.selectedDemoSession = null
    }
  } else {
    state.selectedDemoSession = null
  }
}

async function refresh(): Promise<void> {
  if (state.refreshing) {
    return
  }

  state.refreshing = true
  state.errorMessage = ''
  try {
    const [
      healthPayload,
      metaPayload,
      runtimeStatePayload,
      runtimeSummaryPayload,
      runtimeTimelinePayload,
      runtimeIncidentsPayload,
      runtimeReportPayload,
      systemProfilePayload,
      liveSourcePayload,
    ] = await Promise.all([
      runtimeApi.health(),
      runtimeApi.meta(),
      runtimeApi.state(),
      runtimeApi.summary(),
      runtimeApi.timeline(160),
      runtimeApi.incidents(12),
      runtimeApi.sessionReport(),
      runtimeApi.systemProfile(),
      runtimeApi.liveSource(),
    ])

    state.health = healthPayload
    state.meta = metaPayload
    state.runtimeState = runtimeStatePayload
    state.runtimeSummary = runtimeSummaryPayload
    state.runtimeTimeline = runtimeTimelinePayload
    state.runtimeIncidents = runtimeIncidentsPayload.items.filter(Boolean) as Incident[]
    state.runtimeReport = runtimeReportPayload
    state.systemProfile = systemProfilePayload
    state.liveSource = liveSourcePayload

    await Promise.all([refreshDemos(), refreshArchives()])

    state.lastUpdatedAt = new Date().toLocaleString('zh-CN', { hour12: false })
    state.loading = false
  } catch (error) {
    state.errorMessage = error instanceof Error ? error.message : '运行时服务暂时不可用'
  } finally {
    state.refreshing = false
  }
}

async function loadArchive(sessionId: string): Promise<void> {
  state.selectedArchiveId = sessionId
  state.selectedArchiveReport = await runtimeApi.archiveById(sessionId)
}

async function archiveSession(): Promise<void> {
  await runtimeApi.archiveSession()
  Message.success('本次记录已保存')
  await refresh()
}

async function resetRuntime(): Promise<void> {
  await runtimeApi.reset()
  Message.success('已开始新的记录')
  await refresh()
}

async function selectDemo(filename: string): Promise<void> {
  state.selectedDemoFilename = filename
  state.selectedDemoSession = filename ? await runtimeApi.demoSession(filename) : null
}

function setMode(mode: ViewMode): void {
  state.mode = mode
}

function setArchiveFilterState(next: string): void {
  state.archiveFilterState = next
  void refreshArchives()
}

function setArchiveIncidentsOnly(next: boolean): void {
  state.archiveIncidentsOnly = next
  void refreshArchives()
}

const useLiveRuntime = computed(() => Boolean(state.liveSource?.available))
const displayReport = computed<SessionReport | null>(() =>
  useLiveRuntime.value ? state.runtimeReport : state.selectedDemoSession?.session_report ?? state.runtimeReport,
)
const displayTimeline = computed<TimelineResponse | null>(() =>
  useLiveRuntime.value ? state.runtimeTimeline : state.selectedDemoSession?.timeline ?? state.runtimeTimeline,
)
const displayState = computed<DisplayState>(() =>
  !useLiveRuntime.value && state.selectedDemoSession?.session_report
    ? buildDisplayStateFromReport(state.selectedDemoSession.session_report)
    : buildDisplayStateFromRuntime(state.runtimeState, state.runtimeSummary),
)
const displayIncidents = computed<Incident[]>(() =>
  !useLiveRuntime.value && state.selectedDemoSession?.session_report
    ? buildReportIncidents(state.selectedDemoSession.session_report)
    : state.runtimeIncidents,
)
const quickAnswers = computed<QuickAnswer[]>(() => buildQuickAnswers(displayState.value))
const verdict = computed(() => buildVerdict(displayState.value))
const activeRuntimeChips = computed(() =>
  runtimeChips(state.mode, {
    windowSize: state.meta?.window_size,
    stride: state.meta?.inference_stride,
    device: state.meta?.device,
    featureSet: state.meta?.kinematic_feature_set,
    archiveEnabled: state.meta?.archive_enabled,
    scenePriorLoaded: state.meta?.scene_prior_loaded,
  }),
)
const displaySource = computed(() => {
  if (state.liveSource?.available) {
    return {
      mode: 'live',
      label: state.liveSource.source_label || '实时输入',
      detail: '实时接入',
    }
  }
  if (state.selectedDemoSession) {
    return {
      mode: 'demo',
      label: state.selectedDemoSession.name,
      detail: '模拟监看',
    }
  }
  return {
    mode: 'runtime',
    label: '实时输入',
    detail: '运行时状态流',
  }
})

const liveFrameUrl = computed(() => {
  if (!state.liveSource?.available) {
    return ''
  }
  const version = state.liveSource.updated_at ?? Date.now()
  return `/live-frame?v=${encodeURIComponent(String(version))}`
})
const displayDominantState = computed<GuardState>(() => displayReport.value?.dominant_state ?? displayState.value.predictedState)

function startPolling(): void {
  if (pollingTimer !== null) {
    return
  }
  void refresh()
  pollingTimer = window.setInterval(() => {
    void refresh()
  }, 2000)
}

function stopPolling(): void {
  if (pollingTimer !== null) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

export function useRuntimeStore() {
  return {
    state,
    displayState,
    displayReport,
    displayTimeline,
    displayIncidents,
    quickAnswers,
    verdict,
    activeRuntimeChips,
    displaySource,
    displayDominantState,
    liveFrameUrl,
    refresh,
    selectDemo,
    loadArchive,
    archiveSession,
    resetRuntime,
    setMode,
    setArchiveFilterState,
    setArchiveIncidentsOnly,
    startPolling,
    stopPolling,
  }
}
