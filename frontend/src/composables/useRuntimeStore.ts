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
  LiveIngestStatusResponse,
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
  buildDisplayStateFromRuntime,
  buildDisplayStateFromTimeline,
  buildQuickAnswers,
  buildSessionReportFromTimeline,
  buildTimelineIncidents,
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
  liveIngest: LiveIngestStatusResponse | null
  demoVideos: DemoVideoItem[]
  selectedDemoFilename: string
  selectedDemoSession: DemoSessionResponse | null
  uploadingVideo: boolean
  demoPlaybackTime: number
  demoPlaybackDuration: number
  demoPlaybackStarted: boolean
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
  liveIngest: null,
  demoVideos: [],
  selectedDemoFilename: '',
  selectedDemoSession: null,
  uploadingVideo: false,
  demoPlaybackTime: 0,
  demoPlaybackDuration: 0,
  demoPlaybackStarted: false,
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
let pollingActive = false

function preferredDemoFilename(items: DemoVideoItem[]): string {
  const preferred = items.find((item) => item.filename.includes('fall'))
  return preferred?.filename ?? items[0]?.filename ?? ''
}

function normalizeDemoItem(item: DemoVideoItem): DemoVideoItem {
  return {
    ...item,
    url: runtimeApi.mediaUrl(item.url),
    poster_url: item.poster_url ? runtimeApi.mediaUrl(item.poster_url) : item.poster_url,
  }
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
  const previousSelectedFilename = state.selectedDemoFilename
  const payload = await runtimeApi.demoVideos()
  state.demoVideos = payload.items.map(normalizeDemoItem)
  if (!state.selectedDemoFilename && state.demoVideos.length) {
    state.selectedDemoFilename = preferredDemoFilename(state.demoVideos)
  } else if (state.selectedDemoFilename && !state.demoVideos.some((item) => item.filename === state.selectedDemoFilename)) {
    state.selectedDemoFilename = preferredDemoFilename(state.demoVideos)
  }
  const selectedItem = state.demoVideos.find((item) => item.filename === state.selectedDemoFilename) ?? null
  const canLoadSession = Boolean(selectedItem && selectedItem.processing_status !== 'failed')

  if (state.selectedDemoFilename && canLoadSession) {
    try {
      state.selectedDemoSession = await runtimeApi.demoSession(state.selectedDemoFilename)
    } catch {
      state.selectedDemoSession = null
    }
  } else {
    state.selectedDemoSession = null
  }

  if (previousSelectedFilename !== state.selectedDemoFilename) {
    state.demoPlaybackTime = 0
    state.demoPlaybackDuration = 0
    state.demoPlaybackStarted = false
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
      liveIngestPayload,
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
      runtimeApi.liveIngestStatus(),
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
    state.liveIngest = liveIngestPayload

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
  const demoItem = selectedDemoItem.value
  if (!useLiveRuntime.value && demoItem) {
    if (demoItem.source_kind === 'upload' && demoItem.processing_status === 'processing') {
      Message.warning('这段上传视频还在分析，完成后再保存到历史回看')
      return
    }
    await runtimeApi.archiveSession({ demoFilename: demoItem.filename })
    Message.success('当前所看过程已保存到历史回看')
  } else {
    await runtimeApi.archiveSession()
    Message.success('当前这段已保存到历史回看')
  }
  await refresh()
}

async function resetRuntime(): Promise<void> {
  await runtimeApi.reset()
  Message.success('已重新开始判断')
  await refresh()
}

async function selectDemo(filename: string): Promise<void> {
  state.selectedDemoFilename = filename
  state.demoPlaybackTime = 0
  state.demoPlaybackDuration = 0
  state.demoPlaybackStarted = false
  const item = state.demoVideos.find((entry) => entry.filename === filename)
  if (!filename || item?.processing_status === 'failed') {
    state.selectedDemoSession = null
    return
  }
  try {
    state.selectedDemoSession = await runtimeApi.demoSession(filename)
  } catch {
    state.selectedDemoSession = null
  }
}

async function uploadVideo(file: File): Promise<void> {
  state.uploadingVideo = true
  state.errorMessage = ''
  try {
    const payload = await runtimeApi.uploadVideo(file)
    const item = normalizeDemoItem(payload.item)
    state.selectedDemoFilename = item.filename
    state.selectedDemoSession = null
    state.demoPlaybackTime = 0
    state.demoPlaybackDuration = 0
    state.demoPlaybackStarted = false
    state.demoVideos = [item, ...state.demoVideos.filter((entry) => entry.filename !== item.filename)]
    await refreshDemos()
    await selectDemo(item.filename)
    Message.success('视频已接入，系统开始分析。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '上传失败'
    state.errorMessage = message
    Message.error(message)
  } finally {
    state.uploadingVideo = false
  }
}

async function startLiveIngest(payload: { source: string; sourceLabel?: string }): Promise<void> {
  const source = payload.source.trim()
  if (!source) {
    Message.warning('请输入摄像头编号、RTSP 地址或视频路径')
    return
  }
  state.errorMessage = ''
  await runtimeApi.startLiveIngest({
    source,
    sourceLabel: payload.sourceLabel?.trim() || undefined,
  })
  Message.success('实时接入已启动')
  await refresh()
}

async function stopLiveIngest(): Promise<void> {
  state.errorMessage = ''
  await runtimeApi.stopLiveIngest()
  Message.success('正在停止实时接入')
  await refresh()
}

function updateDemoPlayback(payload: { currentTime: number; duration: number; started: boolean }): void {
  state.demoPlaybackTime = Number.isFinite(payload.currentTime) ? payload.currentTime : 0
  state.demoPlaybackDuration = Number.isFinite(payload.duration) ? payload.duration : 0
  state.demoPlaybackStarted = Boolean(payload.started)
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
const selectedDemoItem = computed<DemoVideoItem | null>(() =>
  state.demoVideos.find((item) => item.filename === state.selectedDemoFilename) ?? null,
)
const demoTimelineItems = computed(() => {
  if (useLiveRuntime.value || !state.selectedDemoSession?.timeline?.items?.length || !state.demoPlaybackStarted) {
    return []
  }
  const cutoff = state.demoPlaybackTime + 0.12
  return state.selectedDemoSession.timeline.items.filter((item) => Number(item.timestamp ?? 0) <= cutoff)
})
const displayReport = computed<SessionReport | null>(() =>
  useLiveRuntime.value
    ? state.runtimeReport
    : state.selectedDemoSession?.session_report
      ? buildSessionReportFromTimeline(state.selectedDemoSession.session_report, demoTimelineItems.value, state.demoPlaybackStarted)
      : null,
)
const displayTimeline = computed<TimelineResponse | null>(() =>
  useLiveRuntime.value
    ? state.runtimeTimeline
    : selectedDemoItem.value
      ? {
        count: demoTimelineItems.value.length,
        items: demoTimelineItems.value,
      }
      : null,
)
const displayState = computed<DisplayState>(() =>
  !useLiveRuntime.value && selectedDemoItem.value
    ? state.selectedDemoSession
      ? buildDisplayStateFromTimeline(demoTimelineItems.value, state.demoPlaybackStarted)
      : {
          predictedState: null,
          riskScore: 0,
          confidence: 0,
          stateProbabilities: {},
          incidentTotal: 0,
          lastIncident: null,
          ready: false,
        }
    : buildDisplayStateFromRuntime(state.runtimeState, state.runtimeSummary),
)
const displayIncidents = computed<Incident[]>(() =>
  !useLiveRuntime.value && selectedDemoItem.value
    ? state.selectedDemoSession
      ? buildTimelineIncidents(demoTimelineItems.value)
      : []
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
    poseQualityScore: useLiveRuntime.value
      ? state.runtimeState?.data_quality?.pose_quality_score ?? state.runtimeSummary?.data_quality?.pose_quality_score
      : undefined,
    meanKeypointConfidence: useLiveRuntime.value
      ? state.runtimeState?.data_quality?.mean_keypoint_confidence ?? state.runtimeSummary?.data_quality?.mean_keypoint_confidence
      : undefined,
    visibleJointRatio: useLiveRuntime.value
      ? state.runtimeState?.data_quality?.visible_joint_ratio ?? state.runtimeSummary?.data_quality?.visible_joint_ratio
      : undefined,
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
  if (selectedDemoItem.value) {
    const sourceLabel = selectedDemoItem.value.original_name || selectedDemoItem.value.name
    const sourceDetail =
      selectedDemoItem.value.source_kind === 'upload'
        ? selectedDemoItem.value.processing_status === 'processing'
          ? '上传分析中'
          : selectedDemoItem.value.processing_status === 'failed'
            ? '上传失败'
            : '上传分析'
        : '模拟监看'
    return {
      mode: 'demo',
      label: sourceLabel,
      detail: sourceDetail,
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
  return runtimeApi.mediaUrl(`/live-frame?v=${encodeURIComponent(String(version))}`)
})
const displayDominantState = computed<GuardState>(() => displayReport.value?.dominant_state ?? displayState.value.predictedState)
const currentDataQuality = computed(() =>
  useLiveRuntime.value ? state.runtimeState?.data_quality ?? state.runtimeSummary?.data_quality ?? null : null,
)

function startPolling(): void {
  if (pollingActive) {
    return
  }
  pollingActive = true
  void refresh().finally(scheduleNextPoll)
}

function stopPolling(): void {
  pollingActive = false
  if (pollingTimer !== null) {
    window.clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

function currentPollingDelay(): number {
  if (state.liveIngest?.status === 'starting' || state.liveIngest?.status === 'running' || state.liveIngest?.status === 'stopping') {
    return 700
  }

  const selectedItem = state.demoVideos.find((item) => item.filename === state.selectedDemoFilename) ?? null
  if (selectedItem?.source_kind === 'upload' && selectedItem.processing_status === 'processing') {
    return 700
  }

  if (state.demoVideos.some((item) => item.source_kind === 'upload' && item.processing_status === 'processing')) {
    return 1000
  }

  return 2000
}

function scheduleNextPoll(): void {
  if (!pollingActive) {
    return
  }
  if (pollingTimer !== null) {
    window.clearTimeout(pollingTimer)
  }
  pollingTimer = window.setTimeout(() => {
    void refresh().finally(scheduleNextPoll)
  }, currentPollingDelay())
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
    currentDataQuality,
    displaySource,
    displayDominantState,
    liveFrameUrl,
    refresh,
    selectDemo,
    uploadVideo,
    startLiveIngest,
    stopLiveIngest,
    loadArchive,
    archiveSession,
    resetRuntime,
    updateDemoPlayback,
    setMode,
    setArchiveFilterState,
    setArchiveIncidentsOnly,
    startPolling,
    stopPolling,
  }
}
