<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { runtimeApi } from '../services/runtimeApi'
import type { DemoVideoItem, GuardState, SessionReport } from '../types/runtime'
import { formatRisk, formatSeconds, stateLabel, stateTone } from '../utils/presenters'

const store = useRuntimeStore()
const router = useRouter()

const reportCache = reactive<Record<string, { loading: boolean; report: SessionReport | null }>>({})

const matrixItems = computed(() =>
  store.state.demoVideos
    .filter((item) => item.processing_status !== 'failed')
    .slice(0, 12),
)

const highRiskItems = computed(() =>
  matrixItems.value.filter((item) => {
    const report = reportCache[item.filename]?.report
    const state = report?.dominant_state ?? null
    const risk = Number(report?.peak_risk?.risk_score ?? 0)
    return state === 'fall' || state === 'prolonged_lying' || risk >= 0.66
  }),
)

const processingCount = computed(() =>
  store.state.demoVideos.filter((item) => item.source_kind === 'upload' && item.processing_status === 'processing').length,
)

const liveStatus = computed(() => {
  if (store.state.liveSource?.available) {
    return {
      title: store.state.liveSource.source_label || '实时输入',
      detail: '连续接入中',
      tone: 'safe' as const,
    }
  }
  if (store.state.liveIngest?.active) {
    return {
      title: store.state.liveIngest.source_label || store.state.liveIngest.source || '实时输入',
      detail: '正在接入',
      tone: 'watch' as const,
    }
  }
  if (store.state.liveIngest?.status === 'failed') {
    return {
      title: store.state.liveIngest.source_label || store.state.liveIngest.source || '实时输入',
      detail: '接入失败',
      tone: 'alert' as const,
    }
  }
  return {
    title: '实时接入',
    detail: '未启动',
    tone: 'neutral' as const,
  }
})

const overviewStats = computed(() => [
  {
    label: '监看源',
    value: String(matrixItems.value.length + (store.state.liveSource?.available ? 1 : 0)),
    detail: '可切换查看的输入源',
  },
  {
    label: '高风险源',
    value: String(highRiskItems.value.length),
    detail: '跌倒、长卧或风险峰值较高',
  },
  {
    label: '分析中',
    value: String(processingCount.value),
    detail: '上传后仍在补全时间线',
  },
  {
    label: '历史留档',
    value: String(store.state.archiveSummary?.archive_total ?? 0),
    detail: '已保存的可复核过程',
  },
])

function displayName(item: DemoVideoItem): string {
  return item.original_name || item.name || item.filename
}

function reportFor(item: DemoVideoItem): SessionReport | null {
  return reportCache[item.filename]?.report ?? null
}

function toneFor(item: DemoVideoItem) {
  if (item.processing_status === 'processing') {
    return 'watch'
  }
  const report = reportFor(item)
  return stateTone(report?.dominant_state ?? null, Number(report?.peak_risk?.risk_score ?? 0))
}

function stateFor(item: DemoVideoItem): GuardState {
  if (item.processing_status === 'processing') {
    return null
  }
  return reportFor(item)?.dominant_state ?? null
}

function peakRiskFor(item: DemoVideoItem): string {
  const report = reportFor(item)
  if (item.processing_status === 'processing') {
    return '分析中'
  }
  return report?.peak_risk ? formatRisk(report.peak_risk.risk_score) : '-'
}

function durationFor(item: DemoVideoItem): string {
  const report = reportFor(item)
  return report ? formatSeconds(report.duration_seconds) : '-'
}

function incidentTextFor(item: DemoVideoItem): string {
  const report = reportFor(item)
  if (!report) {
    return item.processing_status === 'processing' ? '正在补全' : '等待报告'
  }
  return report.incident_total > 0 ? `${report.incident_total} 次提醒` : '未触发正式提醒'
}

async function openItem(item: DemoVideoItem): Promise<void> {
  await store.selectDemo(item.filename)
  await router.push('/live')
}

function handleDeleteDemo(item: DemoVideoItem): void {
  if (!window.confirm('确定要移除该上传视频吗？')) {
    return
  }
  void store.deleteDemoVideo(item.filename)
}

watch(
  () => matrixItems.value.map((item) => `${item.filename}:${item.processing_status}`).join('|'),
  () => {
    for (const item of matrixItems.value) {
      if (item.processing_status !== 'ready' || reportCache[item.filename]) {
        continue
      }
      reportCache[item.filename] = { loading: true, report: null }
      void runtimeApi.demoSession(item.filename)
        .then((payload) => {
          reportCache[item.filename] = { loading: false, report: payload.session_report }
        })
        .catch(() => {
          reportCache[item.filename] = { loading: false, report: null }
        })
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="matrix-page">
    <section class="matrix-hero">
      <div class="hero-copy">
        <span class="eyebrow">监看源总览</span>
        <h2>多路态势墙</h2>
        <p>用于快速查看当前可用输入源、分析状态和风险分布；单路详情在实时值守页展开。</p>
      </div>

      <div class="hero-stats">
        <article v-for="item in overviewStats" :key="item.label" class="hero-stat">
          <small>{{ item.label }}</small>
          <strong>{{ item.value }}</strong>
          <span>{{ item.detail }}</span>
        </article>
      </div>
    </section>

    <section class="ingest-status-band" :data-tone="liveStatus.tone">
      <div>
        <small>实时接入状态</small>
        <strong>{{ liveStatus.title }}</strong>
      </div>
      <span>{{ liveStatus.detail }}</span>
      <a-button type="primary" size="large" @click="router.push('/live')">进入实时接入</a-button>
    </section>

    <transition-group name="tile-fade" tag="section" class="source-grid">
      <article
        v-for="(item, index) in matrixItems"
        :key="item.filename"
        class="source-tile"
        :data-tone="toneFor(item)"
        role="button"
        tabindex="0"
        @click="openItem(item)"
        @keydown.enter.prevent="openItem(item)"
        @keydown.space.prevent="openItem(item)"
      >
        <div class="tile-video">
          <video
            :src="item.url"
            :poster="item.poster_url || undefined"
            muted
            autoplay
            loop
            playsinline
            preload="metadata"
          >
            当前浏览器无法播放该监看源。
          </video>
          <div class="tile-overlay">
            <span>{{ `CAM-${String(index + 1).padStart(2, '0')}` }}</span>
            <span>{{ item.source_kind === 'upload' ? '上传分析' : '模拟监看' }}</span>
          </div>
        </div>

        <div class="tile-body">
          <div class="tile-title">
            <strong>{{ displayName(item) }}</strong>
            <span class="state-pill" :data-tone="toneFor(item)">{{ stateLabel(stateFor(item)) }}</span>
          </div>
          <dl class="tile-metrics">
            <div>
              <dt>峰值风险</dt>
              <dd>{{ peakRiskFor(item) }}</dd>
            </div>
            <div>
              <dt>过程时长</dt>
              <dd>{{ durationFor(item) }}</dd>
            </div>
            <div>
              <dt>提醒</dt>
              <dd>{{ incidentTextFor(item) }}</dd>
            </div>
          </dl>
        </div>

        <div v-if="item.source_kind === 'upload'" class="tile-actions">
          <button type="button" class="tile-delete" @click.stop="handleDeleteDemo(item)">移除上传源</button>
        </div>
      </article>

      <div v-if="!matrixItems.length" class="empty-wall">
        <a-empty>
          <template #description>
            <span>当前没有可用监看源。请先在实时值守页接入摄像头、RTSP 或上传视频。</span>
          </template>
        </a-empty>
      </div>
    </transition-group>
  </section>
</template>

<style scoped>
.matrix-page {
  display: grid;
  gap: var(--space-5);
}

.matrix-hero {
  display: grid;
  grid-template-columns: minmax(0, 0.78fr) minmax(520px, 1.22fr);
  gap: var(--space-6);
  align-items: end;
  padding: var(--space-3) 2px var(--space-4);
  border-bottom: 1px solid var(--color-line-soft);
}

.hero-copy {
  display: grid;
  gap: var(--space-2);
}

.eyebrow {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.hero-copy h2 {
  margin: 0;
  font-size: clamp(34px, 5vw, 72px);
  line-height: 0.96;
  letter-spacing: -0.07em;
}

.hero-copy p {
  max-width: 560px;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.75;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.hero-stat {
  min-height: 136px;
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.hero-stat small,
.ingest-status-band small,
.tile-metrics dt {
  display: block;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.hero-stat strong {
  display: block;
  margin: var(--space-3) 0 var(--space-2);
  font-size: 34px;
  line-height: 1;
  letter-spacing: -0.06em;
}

.hero-stat span,
.tile-metrics dd,
.ingest-status-band span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.ingest-status-band {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  align-items: center;
  padding: var(--space-5) var(--space-6);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.ingest-status-band strong {
  display: block;
  margin-top: 6px;
  font-size: 20px;
  letter-spacing: -0.04em;
}

.ingest-status-band[data-tone='safe'] {
  box-shadow: inset 0 0 0 1px var(--color-ok-line);
}

.ingest-status-band[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px var(--color-watch-line);
}

.ingest-status-band[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px var(--color-alert-line);
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5);
}

.source-tile {
  display: grid;
  gap: var(--space-4);
  padding: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-surface-soft);
  color: inherit;
  text-align: left;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
  transition: transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease, opacity 180ms ease;
}

.source-tile:hover {
  transform: translateY(-3px);
  background: rgba(255, 255, 255, 0.045);
  box-shadow: inset 0 0 0 1px var(--color-accent-soft), var(--shadow-soft);
}

.source-tile:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px var(--color-accent), 0 0 0 2px rgba(121, 212, 231, 0.14);
}

.tile-fade-enter-active,
.tile-fade-leave-active,
.tile-fade-move {
  transition: transform 220ms ease, opacity 220ms ease;
}

.tile-fade-enter-from,
.tile-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.tile-fade-leave-active {
  pointer-events: none;
}


.source-tile[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px var(--color-alert-line), var(--shadow-alert);
}

.source-tile[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px var(--color-watch-line), var(--shadow-watch);
}

.tile-video {
  position: relative;
  aspect-ratio: 16 / 9;
  background: var(--color-bg-strong);
}

.tile-video video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.tile-overlay {
  position: absolute;
  inset: var(--space-4) var(--space-4) auto;
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  pointer-events: none;
}

.tile-overlay span,
.state-pill {
  padding: 7px 10px;
  border-radius: 999px;
  background: var(--color-surface-overlay);
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 800;
}

.tile-body {
  display: grid;
  gap: var(--space-4);
  padding: 0 var(--space-5) var(--space-5);
}

.tile-title {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: start;
}

.tile-title strong {
  min-width: 0;
  font-size: 17px;
  line-height: 1.35;
}

.state-pill[data-tone='safe'] {
  background: var(--color-ok-soft);
  color: var(--color-text-ok);
}

.state-pill[data-tone='watch'] {
  background: var(--color-watch-soft);
  color: var(--color-text-watch);
}

.state-pill[data-tone='alert'] {
  background: var(--color-alert-soft);
  color: var(--color-text-alert);
}

.tile-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
}

.tile-metrics div {
  display: grid;
  gap: 6px;
}

.tile-metrics dd {
  margin: 0;
  font-weight: 700;
}

.tile-actions {
  padding: 0 var(--space-5) var(--space-5);
}

.tile-delete {
  width: 100%;
  min-height: 36px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-alert-soft);
  color: var(--color-text-alert);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.tile-delete:hover {
  background: rgba(255, 140, 144, 0.22);
}

.empty-wall {
  grid-column: 1 / -1;
  display: grid;
  place-items: center;
  min-height: 360px;
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.empty-wall :deep(.arco-empty-description) {
  color: var(--color-text-tertiary);
}

@media (max-width: 1280px) {
  .matrix-hero,
  .source-grid {
    grid-template-columns: 1fr 1fr;
  }

  .hero-stats {
    grid-column: 1 / -1;
  }
}

@media (max-width: 820px) {
  .matrix-hero,
  .source-grid,
  .hero-stats {
    grid-template-columns: 1fr;
  }

  .ingest-status-band {
    align-items: flex-start;
    flex-direction: column;
  }

  .tile-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
