<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DemoVideoItem, SessionReport } from '../types/runtime'
import {
  archiveDisplayName,
  formatArchiveTime,
  formatRisk,
  formatSeconds,
  formatTimestamp,
  incidentLabel,
  stateLabel,
} from '../utils/presenters'
import { matchDemoVideo } from '../utils/media'

type PreviewTab = 'replay' | 'segments' | 'alerts'

const props = defineProps<{
  report: Readonly<SessionReport> | null
  demoVideos: ReadonlyArray<DemoVideoItem>
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const activeTab = ref<PreviewTab>('replay')

watch(
  () => props.report?.session_id ?? props.report?.archived_at ?? props.report?.session_name ?? '',
  () => {
    activeTab.value = 'replay'
  },
)

const matchedVideo = computed(() =>
  matchDemoVideo(props.demoVideos, [props.report?.source_path, props.report?.session_name, props.report?.session_id]),
)
const displayTitle = computed(() =>
  archiveDisplayName(
    props.report?.session_name,
    props.report?.archived_at,
    matchedVideo.value?.original_name || matchedVideo.value?.name || null,
  ),
)
const jumpTargets = computed(() => {
  if (!props.report) {
    return []
  }
  const items: Array<{ key: string; label: string; timestamp: number }> = []
  if (props.report.peak_risk) {
    items.push({
      key: `peak-${props.report.peak_risk.timestamp}`,
      label: `最高风险时刻 · ${formatTimestamp(props.report.peak_risk.timestamp)}`,
      timestamp: props.report.peak_risk.timestamp,
    })
  }
  for (const incident of (props.report.recent_incidents ?? []).slice(0, 4)) {
    items.push({
      key: `${incident.kind}-${incident.timestamp}`,
      label: `${incidentLabel(incident.kind)} · ${formatTimestamp(incident.timestamp)}`,
      timestamp: incident.timestamp,
    })
  }
  return items
})
const segmentItems = computed(() => {
  const items = props.report?.state_segments?.length
    ? props.report.state_segments
    : props.report?.longest_segments ?? []
  return items.slice(0, 8)
})
const topRiskMoments = computed(() => (props.report?.top_risk_moments ?? []).slice(0, 6))
const incidentItems = computed(() => (props.report?.recent_incidents ?? []).slice(0, 6))

function seekTo(timestamp: number | null | undefined) {
  if (!videoRef.value || !Number.isFinite(timestamp)) {
    return
  }
  videoRef.value.currentTime = Math.max(0, Number(timestamp))
  void videoRef.value.play().catch(() => undefined)
}
</script>

<template>
  <section class="preview-card">
    <template v-if="report">
      <header class="preview-head">
        <div>
          <h2>{{ displayTitle }}</h2>
          <p>{{ formatArchiveTime(report.archived_at) }}</p>
        </div>
        <span class="state-pill">{{ stateLabel(report.dominant_state) }}</span>
      </header>

      <div class="topline">
        <article class="stat emphasis">
          <small>这段过程结论</small>
          <strong>{{ stateLabel(report.dominant_state) }}</strong>
        </article>
        <article class="stat">
          <small>持续时长</small>
          <strong>{{ formatSeconds(report.duration_seconds) }}</strong>
        </article>
        <article class="stat">
          <small>正式提醒</small>
          <strong>{{ report.incident_total }}</strong>
        </article>
        <article class="stat">
          <small>最高风险</small>
          <strong>{{ formatRisk(report.peak_risk?.risk_score ?? 0) }}</strong>
        </article>
      </div>

      <div class="lead-copy">
        <strong>{{ report.incident_total > 0 ? '先看监控回放，再核对风险与提醒。' : '先看监控回放，再核对状态切片。' }}</strong>
      </div>

      <a-tabs
        class="preview-tabs"
        :active-key="activeTab"
        @change="activeTab = String($event) as PreviewTab"
      >
        <a-tab-pane key="replay" title="监控回放">
          <section class="tab-panel">
            <div class="section-head">
              <h3>过程回放</h3>
              <span>{{ matchedVideo?.original_name || matchedVideo?.name || '未匹配到演示视频' }}</span>
            </div>
            <div v-if="matchedVideo" class="video-block">
              <div class="video-shell">
                <video
                  ref="videoRef"
                  :key="matchedVideo.filename"
                  class="video"
                  :src="matchedVideo.url"
                  :poster="matchedVideo.poster_url || undefined"
                  controls
                  preload="auto"
                  muted
                  playsinline
                >
                  当前浏览器无法播放这段回看视频。
                </video>
                <div v-if="jumpTargets.length" class="jump-row">
                  <button
                    v-for="item in jumpTargets"
                    :key="item.key"
                    type="button"
                    class="jump-chip"
                    @click="seekTo(item.timestamp)"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="empty-inline">
              当前记录没有可回放的视频源；如原视频已被清理，仍可继续查看状态切片与风险记录。
            </div>
          </section>
        </a-tab-pane>

        <a-tab-pane key="segments" title="状态切片">
          <section class="tab-panel">
            <div class="section-head">
              <h3>状态切片</h3>
              <span>{{ segmentItems.length }} 段</span>
            </div>
            <div v-if="segmentItems.length" class="list">
              <article
                v-for="segment in segmentItems"
                :key="`${segment.state}-${segment.start_timestamp}`"
                class="item"
              >
                <div class="title-row">
                  <strong>{{ stateLabel(segment.state) }}</strong>
                  <span>{{ formatSeconds(segment.duration_seconds) }}</span>
                </div>
                <div class="meta-row">
                  <span>开始 {{ formatTimestamp(segment.start_timestamp) }}</span>
                  <span>结束 {{ formatTimestamp(segment.end_timestamp) }}</span>
                  <span>最高风险 {{ formatRisk(segment.max_risk_score) }}</span>
                </div>
              </article>
            </div>
            <div v-else class="empty-inline">
              当前记录没有可展示的状态切片。
            </div>
          </section>
        </a-tab-pane>

        <a-tab-pane key="alerts" title="风险与警报">
          <section class="tab-panel alerts-grid">
            <div class="panel-col">
              <div class="section-head">
                <h3>高风险时刻</h3>
                <span>{{ topRiskMoments.length }} 个</span>
              </div>
              <div v-if="topRiskMoments.length" class="list compact">
                <article
                  v-for="moment in topRiskMoments"
                  :key="`${moment.predicted_state}-${moment.timestamp}`"
                  class="item"
                >
                  <div class="title-row">
                    <strong>{{ stateLabel(moment.predicted_state) }}</strong>
                    <span>{{ formatTimestamp(moment.timestamp) }}</span>
                  </div>
                  <div class="meta-row">
                    <span>风险 {{ formatRisk(moment.risk_score) }}</span>
                    <span>置信度 {{ formatRisk(moment.confidence) }}</span>
                  </div>
                </article>
              </div>
              <div v-else class="empty-inline">
                当前记录没有高风险时刻。
              </div>
            </div>

            <div class="panel-col">
              <div class="section-head">
                <h3>系统提醒</h3>
                <span>{{ incidentItems.length }} 条</span>
              </div>
              <div v-if="incidentItems.length" class="list compact">
                <article
                  v-for="incident in incidentItems"
                  :key="`${incident.kind}-${incident.timestamp}`"
                  class="item"
                >
                  <div class="title-row">
                    <strong>{{ incidentLabel(incident.kind) }}</strong>
                    <span>{{ formatTimestamp(incident.timestamp) }}</span>
                  </div>
                  <div class="meta-row">
                    <span>置信度 {{ formatRisk(incident.confidence) }}</span>
                  </div>
                </article>
              </div>
              <div v-else class="empty-inline">
                这条记录没有正式提醒。
              </div>
            </div>
          </section>
        </a-tab-pane>
      </a-tabs>
    </template>

    <div v-else class="empty">
      选择一条回看记录后，这里会显示完整过程和关键时刻。
    </div>
  </section>
</template>

<style scoped>
.preview-card {
  display: grid;
  gap: var(--space-5);
}

.preview-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
}

.preview-head h2 {
  margin: 0 0 6px;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.preview-head p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.state-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 700;
}

.topline {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.stat {
  padding: var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.stat.emphasis {
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1px var(--color-accent);
}

.stat small {
  display: block;
  margin-bottom: 8px;
  color: var(--color-text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.stat strong {
  font-size: 22px;
  letter-spacing: -0.04em;
}

.lead-copy {
  display: grid;
  gap: 6px;
}

.lead-copy strong {
  font-size: 14px;
  letter-spacing: -0.02em;
}

.preview-tabs {
  display: grid;
  gap: var(--space-4);
}

.preview-tabs :deep(.arco-tabs-nav::before) {
  background: var(--color-line-soft);
}

.preview-tabs :deep(.arco-tabs-tab) {
  padding-inline: 0;
  margin-right: var(--space-5);
  color: var(--color-text-secondary);
}

.preview-tabs :deep(.arco-tabs-tab-active),
.preview-tabs :deep(.arco-tabs-tab:hover) {
  color: var(--color-text-primary);
}

.preview-tabs :deep(.arco-tabs-tab-title) {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.preview-tabs :deep(.arco-tabs-content) {
  padding-top: var(--space-2);
}

.tab-panel,
.video-block,
.video-shell,
.panel-col {
  display: grid;
  gap: var(--space-4);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
}

.section-head h3 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.section-head span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.video {
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: 360px;
  border-radius: var(--radius-md);
  background: var(--color-bg-strong);
  object-fit: cover;
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.jump-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.jump-chip {
  border: 0;
  padding: 10px 14px;
  border-radius: 999px;
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
  color: var(--color-text-primary);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
}

.jump-chip:hover {
  transform: translateY(-1px);
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1px var(--color-accent);
}

.alerts-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.list {
  display: grid;
  gap: var(--space-3);
}

.list.compact {
  gap: var(--space-2);
}

.item {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--color-line-soft);
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.title-row {
  margin-bottom: 8px;
}

.title-row strong {
  font-size: 15px;
}

.meta-row span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.empty,
.empty-inline {
  display: grid;
  place-items: center;
  min-height: 140px;
  color: var(--color-text-tertiary);
  text-align: center;
}

@media (max-width: 980px) {
  .topline,
  .alerts-grid {
    grid-template-columns: 1fr;
  }

  .video {
    max-height: none;
  }
}
</style>
