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
        <span class="eyebrow">Watch floor</span>
        <h2>监看画面</h2>
      </div>
      <div class="stage-controls">
        <span class="mode-pill">{{ sourceModeLabel }}</span>
        <a-button size="large" @click="emit('reload')">刷新状态</a-button>
      </div>
    </header>

    <div class="stage-rail">
      <article class="rail-card">
        <span>当前值守源</span>
        <strong>{{ sourceLabel }}</strong>
      </article>
      <article class="rail-card">
        <span>输入模式</span>
        <strong>{{ sourceModeLabel }}</strong>
      </article>
      <article class="rail-card">
        <span>当前结论</span>
        <strong>{{ stateLabel(displayState.predictedState) }}</strong>
      </article>
    </div>

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
        class="video"
        :src="selectedVideo.url"
        controls
        autoplay
        muted
        loop
        playsinline
      />
      <div v-else class="video-empty">当前没有可播放的监看源。</div>

      <div class="scan-line" />

      <div class="overlay overlay-top">
        <span class="overlay-chip record-chip">REC</span>
        <span class="overlay-chip">{{ cameraCode }}</span>
        <span class="overlay-chip">{{ sourceLabel }}</span>
        <span class="overlay-chip">{{ stateLabel(displayState.predictedState) }}</span>
        <span class="overlay-chip">{{ clock }}</span>
      </div>

      <div class="overlay overlay-bottom">
        <div class="focus-copy">
          <strong>{{ stateLabel(displayState.predictedState) }}</strong>
          <span>
            {{ props.viewMode === 'xray' ? `风险 ${formatRisk(displayState.riskScore)}` : '固定机位画面正在持续判断人物状态' }}
          </span>
        </div>
        <div class="hud-metrics">
          <span>本段 {{ formatSeconds(report?.duration_seconds ?? 0) }}</span>
          <span>峰值 {{ formatRisk(report?.peak_risk?.risk_score ?? displayState.riskScore) }}</span>
          <span>{{ sourceDetail }}</span>
        </div>
      </div>
    </div>

    <section v-if="!hasLiveSource && monitorFeeds.length" class="feed-section">
      <header class="feed-head">
        <div>
          <span class="eyebrow">Inputs</span>
          <h3>模拟值守源</h3>
        </div>
        <span>{{ monitorFeeds.length }} 路画面</span>
      </header>

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

.stage-head h2,
.feed-head h3 {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.04em;
}

.feed-head h3 {
  font-size: 20px;
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

.stage-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.rail-card {
  padding: 14px 18px;
  border-radius: 20px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.03);
}

.rail-card span {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.rail-card strong {
  font-size: 18px;
  letter-spacing: -0.03em;
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
  box-shadow: inset 0 0 0 1px rgba(255, 94, 98, 0.4), 0 0 0 1px rgba(255, 94, 98, 0.08), 0 0 48px rgba(255, 94, 98, 0.12);
}

.video-shell[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px rgba(255, 179, 71, 0.35), 0 0 0 1px rgba(255, 179, 71, 0.08), 0 0 42px rgba(255, 179, 71, 0.1);
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

.frame-corners {
  position: absolute;
  inset: 18px;
  pointer-events: none;
  z-index: 3;
}

.corner {
  position: absolute;
  width: 30px;
  height: 30px;
  border-color: rgba(67, 215, 255, 0.55);
  border-style: solid;
}

.corner-tl {
  top: 0;
  left: 0;
  border-width: 2px 0 0 2px;
}

.corner-tr {
  top: 0;
  right: 0;
  border-width: 2px 2px 0 0;
}

.corner-bl {
  bottom: 0;
  left: 0;
  border-width: 0 0 2px 2px;
}

.corner-br {
  right: 0;
  bottom: 0;
  border-width: 0 2px 2px 0;
}

.scan-line {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 0%, rgba(67, 215, 255, 0.04) 48%, transparent 100%);
  animation: scan 6s linear infinite;
  pointer-events: none;
  z-index: 2;
}

@keyframes scan {
  from { transform: translateY(-100%); }
  to { transform: translateY(100%); }
}

.overlay {
  position: absolute;
  left: 24px;
  right: 24px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  z-index: 4;
}

.overlay-top {
  top: 24px;
}

.overlay-bottom {
  bottom: 24px;
  align-items: end;
  justify-content: space-between;
}

.overlay-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(5, 11, 19, 0.66);
  border: 1px solid rgba(120, 146, 176, 0.18);
  color: rgba(240, 246, 252, 0.92);
  font-size: 12px;
  font-weight: 700;
  backdrop-filter: blur(14px);
}

.record-chip {
  background: rgba(255, 94, 98, 0.18);
  border-color: rgba(255, 94, 98, 0.3);
  color: #ffd9d4;
}

.focus-copy {
  display: grid;
  gap: 8px;
  max-width: 420px;
}

.focus-copy strong {
  font-size: clamp(28px, 4vw, 48px);
  line-height: 0.92;
  letter-spacing: -0.06em;
}

.focus-copy span {
  color: rgba(222, 232, 243, 0.86);
  font-size: 14px;
}

.hud-metrics {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hud-metrics span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(5, 11, 19, 0.66);
  border: 1px solid rgba(120, 146, 176, 0.18);
  color: rgba(232, 240, 249, 0.88);
  font-size: 12px;
  font-weight: 700;
}

.feed-section {
  display: grid;
  gap: 14px;
}

.feed-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
}

.feed-head span:last-child {
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
}

.feed-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.feed-card {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
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
  border-radius: 14px;
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
  color: rgba(199, 214, 231, 0.68);
  font-size: 12px;
}

@media (max-width: 1100px) {
  .stage-rail,
  .feed-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overlay-bottom {
    gap: 16px;
    align-items: flex-start;
    flex-direction: column;
  }

  .hud-metrics {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .stage-head,
  .feed-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .stage-rail,
  .feed-strip {
    grid-template-columns: 1fr;
  }

  .overlay {
    left: 16px;
    right: 16px;
  }

  .video {
    height: 54vh;
  }
}
</style>
