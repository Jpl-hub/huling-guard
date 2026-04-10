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
    : selectedVideo.value?.name ?? '模拟监看源',
)

const sourceModeLabel = computed(() => (hasLiveSource.value ? '实时接入' : '模拟监看'))

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
        <span class="eyebrow">Monitor</span>
        <h2>监看画面</h2>
      </div>
      <div class="stage-controls">
        <span class="mode-pill">{{ sourceModeLabel }}</span>
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
      <div v-else class="video-empty">当前没有可播放的监看源。</div>

      <div class="overlay overlay-top">
        <span class="overlay-chip record-chip">REC</span>
        <span class="overlay-chip">{{ cameraCode }}</span>
        <span class="overlay-chip">{{ sourceLabel }}</span>
        <span class="overlay-chip">{{ sourceDetail }}</span>
        <span class="overlay-chip status-chip">{{ stateLabel(displayState.predictedState) }}</span>
        <span class="overlay-chip">{{ clock }}</span>
      </div>

      <div class="overlay overlay-bottom">
        <div class="focus-copy">
          <strong>{{ stateLabel(displayState.predictedState) }}</strong>
          <span>{{ props.viewMode === 'xray' ? `风险 ${formatRisk(displayState.riskScore)}` : '固定机位监看输入正在持续分析' }}</span>
        </div>
        <div class="hud-metrics">
          <span>会话 {{ formatSeconds(report?.duration_seconds ?? 0) }}</span>
          <span>峰值 {{ formatRisk(report?.peak_risk?.risk_score ?? displayState.riskScore) }}</span>
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
  align-items: center;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(142, 180, 221, 0.78);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.stage-head h2 {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.04em;
}

.stage-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.mode-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(230, 238, 247, 0.82);
  font-size: 12px;
  font-weight: 700;
}

.video-shell {
  position: relative;
  min-height: 640px;
  overflow: hidden;
  border-radius: 34px;
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
  height: min(78vh, 860px);
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
  right: 24px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.overlay-top {
  top: 24px;
}

.overlay-bottom {
  bottom: 24px;
  justify-content: space-between;
  align-items: end;
}

.overlay-chip {
  width: fit-content;
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(5, 10, 18, 0.74);
  border: 1px solid rgba(140, 166, 194, 0.18);
  color: rgba(236, 243, 250, 0.88);
  font-size: 12px;
  font-weight: 700;
  backdrop-filter: blur(12px);
}

.record-chip {
  background: rgba(255, 76, 90, 0.88);
  border-color: rgba(255, 135, 145, 0.42);
  color: white;
}

.status-chip {
  background: rgba(67, 215, 255, 0.12);
  border-color: rgba(67, 215, 255, 0.2);
}

.focus-copy {
  display: grid;
  gap: 8px;
}

.focus-copy strong {
  font-size: clamp(34px, 4vw, 52px);
  line-height: 0.96;
  letter-spacing: -0.06em;
  text-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
}

.focus-copy span,
.hud-metrics span {
  color: rgba(227, 237, 247, 0.8);
  font-size: 13px;
}

.hud-metrics {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hud-metrics span {
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(5, 10, 18, 0.74);
  border: 1px solid rgba(140, 166, 194, 0.18);
  backdrop-filter: blur(12px);
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
  border-radius: 24px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(8, 17, 30, 0.72);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: transform 180ms ease, border-color 180ms ease, background-color 180ms ease;
}

.feed-card:hover,
.feed-card.active {
  transform: translateY(-2px);
  border-color: rgba(67, 215, 255, 0.24);
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
}

.feed-meta strong {
  font-size: 13px;
  letter-spacing: 0.08em;
}

.feed-meta span {
  color: rgba(199, 214, 231, 0.68);
  font-size: 12px;
}

@media (max-width: 1080px) {
  .feed-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overlay-bottom {
    flex-direction: column;
    align-items: flex-start;
  }

  .hud-metrics {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .stage-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .feed-strip {
    grid-template-columns: 1fr;
  }

  .video-shell {
    min-height: 520px;
  }

  .overlay {
    left: 16px;
    right: 16px;
  }
}
</style>
