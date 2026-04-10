<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { DemoVideoItem, DisplayState, LiveSourceResponse, SessionReport, ViewMode } from '../types/runtime'
import { formatRisk, formatSeconds, stateLabel, stateTone } from '../utils/presenters'

const props = defineProps<{
  demoVideos: ReadonlyArray<DemoVideoItem>
  selectedDemoFilename: string
  liveSource: Readonly<LiveSourceResponse> | null
  liveFrameUrl: string
  displayState: Readonly<DisplayState>
  report: Readonly<SessionReport> | null
  sourceDetail: string
  viewMode: ViewMode
}>()

const emit = defineEmits<{
  reload: []
  selectDemo: [value: string]
}>()
const clock = ref('')

const selectedVideo = computed(() =>
  props.demoVideos.find((item) => item.filename === props.selectedDemoFilename) ?? null,
)
const hasLiveSource = computed(() => Boolean(props.liveSource?.available && props.liveFrameUrl))
const monitorFeeds = computed(() => props.demoVideos.slice(0, 4))
const selectedFeedIndex = computed(() =>
  Math.max(0, props.demoVideos.findIndex((item) => item.filename === props.selectedDemoFilename)),
)

const sourceLabel = computed(() =>
  hasLiveSource.value
    ? props.liveSource?.source_label || '实时输入'
    : selectedVideo.value?.name ?? '运行时输入',
)

const cameraCode = computed(() =>
  hasLiveSource.value ? 'CAM-LIVE' : `CAM-${String(selectedFeedIndex.value + 1).padStart(2, '0')}`,
)

function updateClock() {
  clock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

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
        <span class="eyebrow">Live</span>
        <h2>当前画面</h2>
      </div>
      <div class="stage-controls">
        <div v-if="hasLiveSource" class="live-pill">
          <strong>实时源已接入</strong>
          <span>{{ props.liveSource?.source_label || '实时输入' }}</span>
        </div>
        <a-button size="large" @click="emit('reload')">刷新</a-button>
      </div>
    </header>

    <div class="video-shell" :data-tone="stateTone(displayState.predictedState, displayState.riskScore)">
      <img
        v-if="hasLiveSource"
        class="video live-frame"
        :src="liveFrameUrl"
        alt="实时输入画面"
      />
      <video
        v-else-if="selectedVideo"
        class="video"
        :src="selectedVideo.url"
        controls
        autoplay
        muted
        loop
        playsinline
      />
      <div v-else class="video-empty">当前没有可播放的监控示例。</div>

      <div class="overlay">
        <div class="overlay-topline">
          <span class="overlay-chip record-chip">REC</span>
          <span class="overlay-chip">{{ cameraCode }}</span>
          <span class="overlay-chip">{{ sourceLabel }}</span>
          <span class="overlay-chip">{{ sourceDetail }}</span>
          <span class="overlay-chip status-chip">{{ stateLabel(displayState.predictedState) }}</span>
          <span class="overlay-chip">{{ clock }}</span>
        </div>
        <div class="overlay-main">
          <strong>{{ stateLabel(displayState.predictedState) }}</strong>
          <span>{{ viewMode === 'xray' ? `风险 ${formatRisk(displayState.riskScore)}` : '系统会持续判断当前状态并记录事件' }}</span>
        </div>
        <div v-if="viewMode === 'xray'" class="overlay-meta">
          <span>主导状态 {{ stateLabel(report?.dominant_state ?? displayState.predictedState) }}</span>
          <span>会话时长 {{ formatSeconds(report?.duration_seconds ?? 0) }}</span>
        </div>
      </div>
    </div>

    <div v-if="!hasLiveSource && monitorFeeds.length" class="feed-strip">
      <button
        v-for="(item, index) in monitorFeeds"
        :key="item.filename"
        type="button"
        class="feed-card"
        :class="{ active: item.filename === selectedDemoFilename }"
        @click="emit('selectDemo', item.filename)"
      >
        <video
          class="feed-video"
          :src="item.url"
          muted
          autoplay
          loop
          playsinline
        />
        <div class="feed-meta">
          <strong>{{ `CAM-${String(index + 1).padStart(2, '0')}` }}</strong>
          <span>{{ item.name }}</span>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.stage-panel {
  display: grid;
  gap: 18px;
}

.stage-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(142, 180, 221, 0.78);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.stage-head h2 {
  margin: 0 0 6px;
  font-size: 26px;
  letter-spacing: -0.04em;
}

.stage-head p {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.5;
}

.stage-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.live-pill {
  display: grid;
  gap: 4px;
  min-width: 180px;
  padding: 12px 16px;
  border-radius: 20px;
  background: rgba(67, 215, 255, 0.08);
  border: 1px solid rgba(67, 215, 255, 0.18);
}

.live-pill strong {
  font-size: 13px;
}

.live-pill span {
  color: rgba(214, 229, 244, 0.74);
  font-size: 12px;
}

.video-shell {
  position: relative;
  min-height: 620px;
  overflow: hidden;
  border-radius: 32px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background:
    radial-gradient(circle at top, rgba(67, 215, 255, 0.12), transparent 34%),
    #07111d;
}

.video-shell[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px rgba(255, 94, 98, 0.4), 0 0 0 1px rgba(255, 94, 98, 0.08);
}

.video-shell[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px rgba(255, 179, 71, 0.35), 0 0 0 1px rgba(255, 179, 71, 0.08);
}

.video {
  display: block;
  width: 100%;
  height: min(76vh, 820px);
  object-fit: cover;
  background: #07111d;
}

.live-frame {
  image-rendering: auto;
}

.video-empty {
  display: grid;
  place-items: center;
  min-height: 520px;
  color: rgba(209, 220, 234, 0.72);
  font-size: 14px;
}

.overlay {
  position: absolute;
  left: 24px;
  bottom: 22px;
  display: grid;
  gap: 10px;
  max-width: 56ch;
}

.overlay-topline {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.overlay-chip {
  width: fit-content;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(6, 17, 29, 0.64);
  border: 1px solid rgba(120, 146, 176, 0.18);
  color: #dce8f5;
  font-size: 12px;
  font-weight: 700;
}

.record-chip {
  color: #ffd7d3;
  background: rgba(255, 94, 98, 0.22);
}

.status-chip {
  background: rgba(6, 17, 29, 0.78);
}

.overlay-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #f8fbff;
}

.overlay-main strong {
  font-size: clamp(26px, 4vw, 42px);
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.overlay-main span,
.overlay-meta span {
  color: rgba(231, 239, 249, 0.88);
  font-size: 14px;
}

.overlay-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.feed-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.feed-card {
  display: grid;
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  border-radius: 22px;
  background: rgba(8, 17, 30, 0.72);
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, background-color 180ms ease;
}

.feed-card:hover,
.feed-card.active {
  transform: translateY(-2px);
  border-color: rgba(67, 215, 255, 0.2);
  background: rgba(67, 215, 255, 0.08);
}

.feed-video {
  width: 100%;
  aspect-ratio: 16 / 10;
  border-radius: 16px;
  object-fit: cover;
  background: #07111d;
}

.feed-meta {
  display: grid;
  gap: 4px;
  text-align: left;
}

.feed-meta strong {
  font-size: 13px;
  letter-spacing: 0.08em;
}

.feed-meta span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 12px;
}

@media (max-width: 780px) {
  .stage-head {
    flex-direction: column;
  }

  .video-shell,
  .video-empty {
    min-height: 360px;
  }

  .video {
    height: 360px;
  }

  .feed-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
