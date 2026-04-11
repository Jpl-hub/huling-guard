<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import type {
  DemoVideoItem,
  DisplayState,
  LiveIngestStatusResponse,
  LiveSourceResponse,
  SessionReport,
  ViewMode,
} from '../types/runtime'
import { formatRisk, formatSeconds, stateLabel, stateTone } from '../utils/presenters'

const props = defineProps<{
  demoVideos: ReadonlyArray<DemoVideoItem>
  selectedDemoFilename: string
  liveSource: Readonly<LiveSourceResponse> | null
  liveIngest: Readonly<LiveIngestStatusResponse> | null
  liveFrameUrl: string
  displayState: Readonly<DisplayState>
  report: Readonly<SessionReport> | null
  sourceDetail: string
  uploading: boolean
  viewMode: ViewMode
}>()

const emit = defineEmits<{
  reload: []
  selectDemo: [value: string]
  uploadVideo: [value: File]
  startLiveIngest: [value: { source: string; sourceLabel?: string }]
  stopLiveIngest: []
  playbackUpdate: [value: { currentTime: number; duration: number; started: boolean }]
}>()
const clock = ref('')
const ingestPanelOpen = ref(false)
const ingestSource = ref('')
const ingestSourceLabel = ref('')
const mainVideoError = ref('')
const mainVideoRef = ref<HTMLVideoElement | null>(null)
const preferRawPlayback = ref(false)
const uploadInputRef = ref<HTMLInputElement | null>(null)
const isVideoPlaying = ref(false)
const videoCurrent = ref(0)
const videoDuration = ref(0)
const playbackStarted = ref(false)
const feedVideoErrors = reactive<Record<string, boolean>>({})

const selectedVideo = computed(() =>
  props.demoVideos.find((item) => item.filename === props.selectedDemoFilename) ?? null,
)
const hasLiveSource = computed(() => Boolean(props.liveSource?.available && props.liveFrameUrl))
const hasRunningIngest = computed(() => Boolean(props.liveIngest?.active))
const ingestStatusText = computed(() => {
  switch (props.liveIngest?.status) {
    case 'starting':
      return '正在连接输入源'
    case 'running':
      return '实时接入中'
    case 'stopping':
      return '正在停止'
    case 'completed':
      return '本次接入已结束'
    case 'failed':
      return '实时接入失败'
    case 'stopped':
      return '实时接入已停止'
    default:
      return '尚未启动'
  }
})
const monitorFeeds = computed(() => {
  const selected = selectedVideo.value ? [selectedVideo.value] : []
  const remaining = props.demoVideos.filter((item) => item.filename !== props.selectedDemoFilename)
  return [...selected, ...remaining.slice(-3)].slice(0, 4)
})
const selectedFeedIndex = computed(() =>
  Math.max(0, props.demoVideos.findIndex((item) => item.filename === props.selectedDemoFilename)),
)

const hasAnnotatedPlayback = computed(() =>
  Boolean(
    !preferRawPlayback.value
      && !hasLiveSource.value
      && selectedVideo.value?.processing_status === 'ready'
      && selectedVideo.value?.annotated_url
      && (props.viewMode === 'xray' || selectedVideo.value?.source_kind === 'upload'),
  ),
)
const selectedPlaybackUrl = computed(() =>
  hasAnnotatedPlayback.value ? selectedVideo.value?.annotated_url || selectedVideo.value?.url || '' : selectedVideo.value?.url || '',
)
const selectedPlaybackKey = computed(() =>
  `${selectedVideo.value?.filename || 'none'}:${props.viewMode}:${hasAnnotatedPlayback.value ? 'annotated' : 'raw'}`,
)

const sourceLabel = computed(() =>
  hasLiveSource.value
    ? props.liveSource?.source_label || '实时输入'
    : hasRunningIngest.value
      ? props.liveIngest?.source_label || props.liveIngest?.source || '实时输入'
      : selectedVideo.value?.original_name || selectedVideo.value?.name || '模拟监看源',
)

const sourceModeLabel = computed(() => {
  if (hasLiveSource.value) {
    return '实时接入'
  }
  if (hasRunningIngest.value) {
    return '正在接入'
  }
  return selectedVideo.value?.source_kind === 'upload' ? '上传分析' : '模拟监看'
})

const cameraCode = computed(() =>
  hasLiveSource.value || hasRunningIngest.value
    ? 'CAM-LIVE'
    : `CAM-${String(selectedFeedIndex.value + 1).padStart(2, '0')}`,
)

const sourceStatus = computed(() => {
  if (hasLiveSource.value) {
    return { label: '实时源状态', value: '连续接入中', tone: 'healthy' as const }
  }
  if (hasRunningIngest.value) {
    return { label: '实时源状态', value: ingestStatusText.value, tone: 'watch' as const }
  }
  if (props.liveIngest?.status === 'failed') {
    return { label: '实时源状态', value: '接入失败', tone: 'alert' as const }
  }
  if (selectedVideo.value?.processing_status === 'processing') {
    const processed = Number(selectedVideo.value.processed_frames ?? 0)
    const stageValue =
      processed <= 0
        ? '正在读取视频'
        : props.displayState.ready || (props.report?.ready_frames ?? 0) > 0
          ? '正在形成正式结论'
          : '正在建立时序窗口'
    return { label: '分析状态', value: stageValue, tone: 'watch' as const }
  }
  if (selectedVideo.value?.processing_status === 'failed') {
    return { label: '分析状态', value: '分析失败', tone: 'alert' as const }
  }
  if (selectedVideo.value?.source_kind === 'upload') {
    return { label: '分析状态', value: '分析完成', tone: 'healthy' as const }
  }
  if (mainVideoError.value) {
    return { label: '监看源状态', value: '加载失败', tone: 'alert' as const }
  }
  return { label: '监看源状态', value: isVideoPlaying.value ? '正在播放' : '点击播放', tone: 'healthy' as const }
})

const sourcePathLabel = computed(() =>
  hasLiveSource.value
    ? props.liveSource?.source_label || '实时输入'
    : hasRunningIngest.value
      ? props.liveIngest?.source_label || props.liveIngest?.source || '实时输入'
      : selectedVideo.value?.source_kind === 'upload'
        ? `上传视频 · ${selectedVideo.value.original_name || selectedVideo.value.filename}`
        : selectedVideo.value
          ? `固定机位样例流 · ${selectedVideo.value.filename}`
          : '当前没有可用视频源',
)
const sourceIngressLabel = computed(() =>
  hasLiveSource.value
    ? '摄像头 / RTSP 推流'
    : hasRunningIngest.value || props.liveIngest?.status === 'failed'
      ? '实时接入管理'
      : selectedVideo.value?.source_kind === 'upload'
        ? '上传后异步分析'
        : '模拟监看流回放',
)
const videoProgress = computed(() =>
  videoDuration.value > 0 ? Math.min(100, Math.max(0, (videoCurrent.value / videoDuration.value) * 100)) : 0,
)
const videoTimeLabel = computed(() =>
  videoDuration.value > 0
    ? `${formatSeconds(videoCurrent.value)} / ${formatSeconds(videoDuration.value)}`
    : '等待画面',
)
const playbackActionLabel = computed(() => (isVideoPlaying.value ? '暂停画面' : '播放并开始判断'))
const analysisCopy = computed(() => {
  if (selectedVideo.value?.processing_status === 'failed') {
    return selectedVideo.value.error_message || '这段上传视频分析失败，请更换视频后重试。'
  }
  if (selectedVideo.value?.processing_status === 'processing') {
    const processed = Number(selectedVideo.value?.processed_frames ?? 0)
    if (processed <= 0) {
      return '视频已经接入，系统正在读取画面并准备启动逐帧推理。'
    }
    if (props.displayState.ready || (props.report?.ready_frames ?? 0) > 0) {
      return '系统已经进入分析阶段，正在继续补全这段视频的状态时间线。'
    }
    return '系统已经开始逐帧提取骨架，正在建立第一段连续时序判断。'
  }
  return ''
})

const focusStateLabel = computed(() => {
  if (selectedVideo.value?.processing_status === 'processing' && !props.displayState.ready) {
    return (props.report?.ready_frames ?? 0) > 0 ? '正在形成结论' : '时序预热中'
  }
  return stateLabel(props.displayState.predictedState)
})

const focusStageText = computed(() => {
  if (hasLiveSource.value) {
    return '实时画面接入中'
  }
  if (hasRunningIngest.value) {
    return '正在等待实时画面进入'
  }
  if (selectedVideo.value?.source_kind === 'upload') {
    if (selectedVideo.value.processing_status === 'processing') {
      return Number(selectedVideo.value.processed_frames ?? 0) > 0
        ? props.displayState.ready || (props.report?.ready_frames ?? 0) > 0
          ? '已进入分析，正在继续补全时间线'
          : '已开始分析，正在建立时序窗口'
        : '视频已接入，正在准备分析'
    }
    return '正在播放上传视频回放'
  }
  return '正在播放固定机位监看流'
})

const uploadProgressRatio = computed(() => {
  const total = Number(selectedVideo.value?.total_frames ?? 0)
  const processed = Number(selectedVideo.value?.processed_frames ?? 0)
  if (total <= 0 || processed <= 0) {
    return 0
  }
  return Math.min(100, Math.max(0, (processed / total) * 100))
})

const uploadProgressText = computed(() => {
  const total = Number(selectedVideo.value?.total_frames ?? 0)
  const processed = Number(selectedVideo.value?.processed_frames ?? 0)
  if (total > 0) {
    return `已处理 ${processed} / ${total} 帧`
  }
  if (processed > 0) {
    return `已处理 ${processed} 帧`
  }
  return '正在建立分析任务'
})

const liveIngestHint = computed(() =>
  props.liveIngest?.error_message || '支持 RTSP 地址、设备编号 0，或容器内可访问的视频路径。',
)

function submitLiveIngest() {
  const source = ingestSource.value.trim()
  if (!source) {
    return
  }
  emit('startLiveIngest', {
    source,
    sourceLabel: ingestSourceLabel.value.trim() || undefined,
  })
}

function requestStopLiveIngest() {
  emit('stopLiveIngest')
}

function markMainVideoLoaded() {
  mainVideoError.value = ''
  syncVideoState()
}

function markMainVideoReady() {
  markMainVideoLoaded()
}

function markMainVideoFailed() {
  if (hasAnnotatedPlayback.value && !preferRawPlayback.value && selectedVideo.value?.url) {
    preferRawPlayback.value = true
    mainVideoError.value = ''
    window.setTimeout(() => {
      syncVideoState()
    }, 0)
    return
  }
  mainVideoError.value = '这段监看流暂时没有加载出来，可以先点“刷新状态”再试一次。'
}

function syncVideoState() {
  const video = mainVideoRef.value
  if (!video) {
    return
  }
  videoCurrent.value = Number.isFinite(video.currentTime) ? video.currentTime : 0
  videoDuration.value = Number.isFinite(video.duration) ? video.duration : 0
  isVideoPlaying.value = !video.paused && !video.ended
  playbackStarted.value = playbackStarted.value || isVideoPlaying.value || videoCurrent.value > 0.05
  emit('playbackUpdate', {
    currentTime: videoCurrent.value,
    duration: videoDuration.value,
    started: playbackStarted.value,
  })
}

async function togglePlayback() {
  const video = mainVideoRef.value
  if (!video) {
    return
  }
  try {
    if (video.paused || video.ended) {
      await video.play()
    } else {
      video.pause()
    }
    syncVideoState()
  } catch {
    markMainVideoFailed()
  }
}

function openUploadPicker() {
  uploadInputRef.value?.click()
}

function handleUploadSelection(event: Event) {
  const target = event.target as HTMLInputElement | null
  const file = target?.files?.[0]
  if (!file) {
    return
  }
  emit('uploadVideo', file)
  target.value = ''
}

function markFeedVideoLoaded(filename: string) {
  delete feedVideoErrors[filename]
}

function markFeedVideoFailed(filename: string) {
  feedVideoErrors[filename] = true
}

function updateClock() {
  clock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

watch(() => [props.selectedDemoFilename, props.viewMode] as const, () => {
  preferRawPlayback.value = false
  mainVideoError.value = ''
  isVideoPlaying.value = false
  videoCurrent.value = 0
  videoDuration.value = 0
  playbackStarted.value = false
  emit('playbackUpdate', { currentTime: 0, duration: 0, started: false })
  window.setTimeout(() => {
    syncVideoState()
  }, 0)
})

let timer: number | null = null

onMounted(() => {
  updateClock()
  timer = window.setInterval(updateClock, 1000)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <section class="stage-panel">
    <header class="stage-head">
      <div>
        <h2>当前画面</h2>
        <p>{{ sourceModeLabel }} · {{ sourceLabel }}</p>
      </div>
      <div class="stage-controls">
        <span class="mode-pill">{{ cameraCode }}</span>
        <a-button size="large" @click="ingestPanelOpen = !ingestPanelOpen">实时接入</a-button>
        <a-button size="large" :loading="uploading" @click="openUploadPicker">上传视频分析</a-button>
        <a-button size="large" @click="emit('reload')">刷新状态</a-button>
        <input
          ref="uploadInputRef"
          class="file-input"
          type="file"
          accept="video/mp4"
          @change="handleUploadSelection"
        />
      </div>
    </header>

    <section v-if="ingestPanelOpen || hasRunningIngest || liveIngest?.status === 'failed'" class="ingest-panel">
      <div class="ingest-copy">
        <h3>实时接入</h3>
        <p>接入摄像头、RTSP 或视频文件后，系统将切换到该输入源进行连续分析。</p>
      </div>

      <div class="ingest-form">
        <label>
          <span>输入源</span>
          <a-input v-model="ingestSource" size="large" placeholder="例如 rtsp://...、0、/runtime-demo/videos/fall_01_demo.mp4" />
        </label>
        <label>
          <span>显示名称</span>
          <a-input v-model="ingestSourceLabel" size="large" placeholder="例如 客厅摄像头 / 房间 A" />
        </label>
      </div>

      <div class="ingest-bar">
        <div class="ingest-status" :data-state="liveIngest?.status || 'idle'">
          <strong>{{ ingestStatusText }}</strong>
          <span>{{ liveIngestHint }}</span>
        </div>

        <div class="ingest-actions">
          <a-button v-if="hasRunningIngest" size="large" status="danger" @click="requestStopLiveIngest">停止接入</a-button>
          <a-button v-else type="primary" size="large" @click="submitLiveIngest">启动接入</a-button>
        </div>
      </div>
    </section>

    <div class="video-shell" :data-tone="stateTone(displayState.predictedState, displayState.riskScore)">
      <div class="frame-corners">
        <span class="corner corner-tl" />
        <span class="corner corner-tr" />
        <span class="corner corner-bl" />
        <span class="corner corner-br" />
      </div>

      <img
        v-if="hasLiveSource"
        class="video live-frame"
        :src="liveFrameUrl"
        alt="实时输入画面"
      />
      <video
        v-else-if="selectedVideo"
        ref="mainVideoRef"
        :key="selectedPlaybackKey"
        class="video"
        :src="selectedPlaybackUrl"
        :poster="selectedVideo.poster_url || undefined"
        muted
        playsinline
        preload="auto"
        @click="togglePlayback"
        @loadeddata="markMainVideoReady"
        @loadedmetadata="syncVideoState"
        @canplay="markMainVideoReady"
        @timeupdate="syncVideoState"
        @play="syncVideoState"
        @pause="syncVideoState"
        @error="markMainVideoFailed"
      >
        当前浏览器无法播放这段监看流。
      </video>
      <div v-else class="video-empty">当前没有可播放的监看源。</div>
      <div v-if="!hasLiveSource && selectedVideo" class="playback-panel">
        <button type="button" class="playback-button" @click.stop="togglePlayback">
          {{ playbackActionLabel }}
        </button>
        <div class="playback-progress" aria-hidden="true">
          <span :style="{ width: `${videoProgress}%` }" />
        </div>
        <span class="playback-time">{{ videoTimeLabel }}</span>
      </div>

      <div class="overlay overlay-top">
        <span class="overlay-chip record-chip">REC</span>
        <span class="overlay-chip">{{ cameraCode }}</span>
        <span class="overlay-chip">{{ sourceModeLabel }}</span>
        <span v-if="hasAnnotatedPlayback" class="overlay-chip">骨架/框叠加回放</span>
        <span class="overlay-chip">{{ clock }}</span>
      </div>

      <div class="overlay overlay-bottom">
        <div class="focus-copy">
          <strong>{{ focusStateLabel }}</strong>
          <span>{{ focusStageText }}</span>
        </div>
        <div class="hud-metrics">
          <span>本段 {{ formatSeconds(report?.duration_seconds ?? 0) }}</span>
          <span>峰值 {{ formatRisk(report?.peak_risk?.risk_score ?? displayState.riskScore) }}</span>
          <span>{{ sourceDetail }}</span>
        </div>
      </div>

      <div v-if="mainVideoError" class="video-warning">
        <strong>画面加载失败</strong>
        <span>{{ mainVideoError }}</span>
      </div>

      <div
        v-if="!hasLiveSource && selectedVideo?.source_kind === 'upload' && selectedVideo.processing_status !== 'ready'"
        class="analysis-status"
        :data-tone="selectedVideo.processing_status === 'failed' ? 'alert' : 'watch'"
      >
        <strong>{{ selectedVideo.processing_status === 'failed' ? '上传视频未完成分析' : '上传视频分析中' }}</strong>
        <span>{{ analysisCopy }}</span>
        <span>{{ uploadProgressText }}</span>
        <div v-if="selectedVideo.processing_status === 'processing'" class="analysis-progress" aria-hidden="true">
          <span :style="{ width: `${uploadProgressRatio}%` }" />
        </div>
      </div>
    </div>

    <section class="source-strip">
      <div class="source-card">
        <small>{{ sourceStatus.label }}</small>
        <strong :data-tone="sourceStatus.tone">{{ sourceStatus.value }}</strong>
      </div>
      <div class="source-card source-path">
        <small>当前输入源</small>
        <strong>{{ sourceLabel }}</strong>
        <span>{{ sourcePathLabel }}</span>
      </div>
      <div class="source-card">
        <small>接入方式</small>
        <strong>{{ sourceIngressLabel }}</strong>
      </div>
    </section>

    <section v-if="!hasLiveSource && monitorFeeds.length" class="feed-section">
      <div class="feed-head">
        <h3>切换监看源</h3>
        <span>{{ monitorFeeds.length }} 路</span>
      </div>

      <div class="feed-strip">
        <button
          v-for="(item, index) in monitorFeeds"
          :key="item.filename"
          type="button"
          class="feed-card"
          :class="{ active: item.filename === selectedDemoFilename }"
          @click="emit('selectDemo', item.filename)"
        >
          <video
            :key="item.filename"
            class="feed-video"
            :src="item.url"
            :poster="item.poster_url || undefined"
            muted
            autoplay
            loop
            playsinline
            preload="metadata"
            @loadeddata="markFeedVideoLoaded(item.filename)"
            @error="markFeedVideoFailed(item.filename)"
          >
            当前浏览器无法播放缩略监看流。
          </video>
          <div v-if="feedVideoErrors[item.filename]" class="feed-error">源不可用</div>
          <div class="feed-meta">
            <div class="feed-meta-row">
              <strong>{{ `CAM-${String(index + 1).padStart(2, '0')}` }}</strong>
              <span
                v-if="item.source_kind === 'upload'"
                class="feed-badge"
                :data-state="item.processing_status || 'ready'"
              >
                {{ item.processing_status === 'processing' ? '分析中' : item.processing_status === 'failed' ? '失败' : '上传' }}
              </span>
            </div>
            <span>{{ item.original_name || item.name }}</span>
          </div>
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.stage-panel {
  display: grid;
  gap: var(--space-4);
}

.stage-head,
.feed-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: center;
}

.stage-head h2,
.feed-head h3 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.feed-head h3 {
  font-size: 16px;
}

.stage-head p,
.feed-head span {
  margin: var(--space-1) 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.stage-controls {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
}

.ingest-panel {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  border-top: 1px solid var(--color-line-soft);
  background: var(--color-surface-soft);
}

.ingest-copy {
  display: grid;
  gap: var(--space-1);
}

.ingest-copy h3 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.03em;
}

.ingest-copy p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.ingest-form {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(220px, 0.8fr);
  gap: var(--space-4);
}

.ingest-form label {
  display: grid;
  gap: var(--space-2);
}

.ingest-form span,
.ingest-status span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.ingest-bar {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: center;
}

.ingest-status {
  display: grid;
  gap: var(--space-1);
}

.ingest-status strong {
  font-size: 15px;
}

.ingest-status[data-state='failed'] strong {
  color: var(--color-alert);
}

.ingest-status[data-state='running'] strong,
.ingest-status[data-state='starting'] strong,
.ingest-status[data-state='stopping'] strong {
  color: var(--color-watch);
}

.ingest-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.file-input {
  display: none;
}

.mode-pill,
.overlay-chip {
  padding: 9px 13px;
  border-radius: 999px;
  background: var(--color-surface-overlay);
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 700;
}

.video-shell {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--color-bg-strong);
  box-shadow: var(--shadow-stage);
}

.video-shell[data-tone='alert'] {
  box-shadow: var(--shadow-alert);
}

.video-shell[data-tone='watch'] {
  box-shadow: var(--shadow-watch);
}

.video,
.live-frame,
.video-empty {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  background: var(--color-bg-strong);
}

.video,
.live-frame {
  object-fit: cover;
}

.video-empty {
  display: grid;
  place-items: center;
  color: var(--color-text-secondary);
  font-size: 15px;
}

.frame-corners {
  pointer-events: none;
}

.corner {
  position: absolute;
  width: 34px;
  height: 34px;
  border-color: var(--color-accent);
  border-style: solid;
  z-index: 2;
}

.corner-tl {
  top: var(--space-5);
  left: var(--space-5);
  border-width: 3px 0 0 3px;
  border-top-left-radius: var(--radius-sm);
}

.corner-tr {
  top: var(--space-5);
  right: var(--space-5);
  border-width: 3px 3px 0 0;
  border-top-right-radius: var(--radius-sm);
}

.corner-bl {
  left: var(--space-5);
  bottom: var(--space-5);
  border-width: 0 0 3px 3px;
  border-bottom-left-radius: var(--radius-sm);
}

.corner-br {
  right: var(--space-5);
  bottom: var(--space-5);
  border-width: 0 3px 3px 0;
  border-bottom-right-radius: var(--radius-sm);
}

.overlay {
  position: absolute;
  left: var(--space-6);
  right: var(--space-6);
  z-index: 3;
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.overlay-top {
  top: var(--space-6);
}

.overlay-bottom {
  bottom: var(--space-6);
  align-items: end;
}

.video-warning {
  position: absolute;
  left: var(--space-6);
  bottom: 172px;
  z-index: 4;
  display: grid;
  gap: var(--space-1);
  max-width: 380px;
  padding: 14px var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--color-surface-overlay);
  box-shadow: inset 0 0 0 1px var(--color-alert-line), var(--shadow-soft);
}

.video-warning strong {
  font-size: 15px;
}

.video-warning span {
  color: var(--color-text-alert);
  font-size: 13px;
  line-height: 1.5;
}

.analysis-status {
  position: absolute;
  left: var(--space-6);
  top: 88px;
  z-index: 4;
  display: grid;
  gap: var(--space-1);
  max-width: 420px;
  padding: 14px var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--color-surface-overlay);
  box-shadow: var(--shadow-soft);
}

.analysis-status[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px var(--color-watch-line), var(--shadow-soft);
}

.analysis-status[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px var(--color-alert-line), var(--shadow-soft);
}

.analysis-status span {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.analysis-progress {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--color-surface-soft);
}

.analysis-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-watch);
}

.record-chip {
  color: var(--color-alert);
}

.playback-panel {
  position: absolute;
  left: var(--space-6);
  right: var(--space-6);
  bottom: 110px;
  z-index: 4;
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 999px;
  background: var(--color-surface-overlay);
  box-shadow: inset 0 0 0 1px var(--color-line-soft), var(--shadow-soft);
}

.playback-button {
  border: 0;
  border-radius: 999px;
  padding: 10px 14px;
  background: var(--color-text-primary);
  color: var(--color-bg-strong);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.playback-progress {
  position: relative;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
}

.playback-progress span {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: var(--color-ok);
}

.playback-time {
  color: var(--color-text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.focus-copy {
  display: grid;
  gap: var(--space-1);
}

.focus-copy strong {
  font-size: clamp(30px, 3.8vw, 54px);
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.focus-copy span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.hud-metrics {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hud-metrics span {
  padding: 10px 12px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.34);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.source-strip {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) 180px;
  gap: var(--space-3);
}

.source-card {
  display: grid;
  gap: var(--space-2);
  padding: 14px 0 0;
  border-top: 1px solid var(--color-line-soft);
  background: transparent;
}

.source-card small {
  color: var(--color-text-tertiary);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.source-card strong {
  font-size: 18px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.source-card strong[data-tone='alert'] {
  color: var(--color-alert);
}

.source-card strong[data-tone='healthy'] {
  color: var(--color-ok);
}

.source-card strong[data-tone='watch'] {
  color: var(--color-watch);
}

.source-card span {
  color: var(--color-text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-path {
  min-width: 0;
}

.feed-section {
  display: grid;
  gap: var(--space-3);
}

.feed-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.feed-card {
  position: relative;
  display: grid;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease;
}

.feed-card:hover,
.feed-card.active {
  transform: translateY(-2px);
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-strong);
}

.feed-video {
  width: 100%;
  aspect-ratio: 16 / 10;
  border-radius: var(--radius-sm);
  object-fit: cover;
  background: var(--color-bg-strong);
}

.feed-error {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  z-index: 2;
  padding: 6px 8px;
  border-radius: 999px;
  background: var(--color-alert-soft);
  color: var(--color-text-alert);
  font-size: 11px;
  font-weight: 700;
}

.feed-meta {
  display: grid;
  gap: var(--space-1);
}

.feed-meta-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  align-items: center;
}

.feed-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--color-surface-soft);
  color: var(--color-text-secondary);
  font-size: 11px;
  line-height: 1;
}

.feed-badge[data-state='processing'] {
  background: var(--color-watch-soft);
  color: var(--color-text-watch);
}

.feed-badge[data-state='failed'] {
  background: var(--color-alert-soft);
  color: var(--color-text-alert);
}

.feed-meta strong {
  font-size: 13px;
}

.feed-meta span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

@media (max-width: 980px) {
  .ingest-form {
    grid-template-columns: 1fr;
  }

  .ingest-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .source-strip {
    grid-template-columns: 1fr;
  }

  .feed-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .stage-head,
  .feed-head,
  .overlay,
  .overlay-bottom {
    flex-direction: column;
    align-items: flex-start;
  }

  .overlay {
    left: var(--space-4);
    right: var(--space-4);
  }

  .overlay-top {
    top: var(--space-4);
  }

  .overlay-bottom {
    bottom: var(--space-4);
  }

  .analysis-status,
  .video-warning {
    left: var(--space-4);
    max-width: calc(100% - var(--space-8));
  }

  .playback-panel {
    left: var(--space-4);
    right: var(--space-4);
    grid-template-columns: 1fr;
    border-radius: var(--radius-md);
  }

  .feed-strip {
    grid-template-columns: 1fr;
  }
}
</style>
