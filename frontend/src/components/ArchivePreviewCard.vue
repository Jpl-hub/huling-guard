<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DemoVideoItem, SessionReport } from '../types/runtime'
import { formatArchiveTime, formatRisk, formatSeconds, formatTimestamp, incidentLabel, stateLabel } from '../utils/presenters'

const props = defineProps<{
  report: Readonly<SessionReport> | null
  demoVideos: ReadonlyArray<DemoVideoItem>
}>()

const videoRef = ref<HTMLVideoElement | null>(null)

const matchedVideo = computed(() => {
  if (!props.report?.source_path) {
    return null
  }
  const normalizedSource = props.report.source_path.replace(/\\/g, '/')
  const sourceName = normalizedSource.split('/').pop() ?? ''
  const sourceStem = sourceName.replace(/\.mp4$/i, '')
  return (
    props.demoVideos.find((item) => item.filename === sourceName)
    ?? props.demoVideos.find((item) => item.name === sourceStem)
    ?? null
  )
})

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
          <h2>{{ report.session_name || '历史记录' }}</h2>
          <p>{{ formatArchiveTime(report.archived_at) }}</p>
        </div>
        <span class="state-pill">{{ stateLabel(report.dominant_state) }}</span>
      </header>

      <div v-if="matchedVideo" class="video-block">
        <div class="video-head">
          <h3>过程视频</h3>
          <span>{{ matchedVideo.name }}</span>
        </div>
        <div class="video-shell">
          <video
            ref="videoRef"
            class="video"
            :src="matchedVideo.url"
            controls
            preload="metadata"
            muted
            playsinline
          />
          <div class="jump-row">
            <button
              v-if="report.peak_risk"
              type="button"
              class="jump-chip"
              @click="seekTo(report.peak_risk.timestamp)"
            >
              跳到最高风险时刻
            </button>
            <button
              v-for="incident in (report.recent_incidents ?? []).slice(0, 3)"
              :key="`${incident.kind}-${incident.timestamp}`"
              type="button"
              class="jump-chip"
              @click="seekTo(incident.timestamp)"
            >
              {{ incidentLabel(incident.kind) }} · {{ formatTimestamp(incident.timestamp) }}
            </button>
          </div>
        </div>
      </div>

      <div class="topline">
        <article class="stat">
          <small>记录时长</small>
          <strong>{{ formatSeconds(report.duration_seconds) }}</strong>
        </article>
        <article class="stat">
          <small>累计事件</small>
          <strong>{{ report.incident_total }}</strong>
        </article>
        <article class="stat">
          <small>峰值风险</small>
          <strong>{{ formatRisk(report.peak_risk?.risk_score ?? 0) }}</strong>
        </article>
      </div>

      <div class="section">
        <h3>关键阶段</h3>
        <div class="list">
          <article
            v-for="segment in (report.longest_segments ?? []).slice(0, 4)"
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
      </div>

      <div class="section">
        <h3>风险高点</h3>
        <div class="list">
          <article
            v-for="moment in (report.top_risk_moments ?? []).slice(0, 5)"
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
      </div>

      <div class="section">
        <h3>最近事件</h3>
        <div class="list">
          <article
            v-for="incident in (report.recent_incidents ?? []).slice(0, 4)"
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
          <div v-if="!report.recent_incidents?.length" class="empty-inline">
            这条记录没有正式事件。
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty">
      选择一条历史会话后，这里会显示完整预览。
    </div>
  </section>
</template>

<style scoped>
.preview-card {
  display: grid;
  gap: 22px;
}

.video-block {
  display: grid;
  gap: 14px;
}

.video-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.video-head h3 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.video-head span {
  color: rgba(199, 214, 231, 0.68);
  font-size: 12px;
}

.video-shell {
  display: grid;
  gap: 12px;
}

.video {
  width: 100%;
  max-height: 420px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: #07111d;
  object-fit: cover;
}

.jump-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.jump-chip {
  border: 0;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(232, 240, 249, 0.88);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 180ms ease, transform 180ms ease;
}

.jump-chip:hover {
  transform: translateY(-1px);
  background: rgba(67, 215, 255, 0.12);
}

.preview-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.preview-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  letter-spacing: -0.04em;
}

.preview-head p {
  margin: 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 13px;
}

.state-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.14);
  color: #d9f7ff;
  font-size: 13px;
  font-weight: 700;
}

.topline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.stat,
.item {
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
}

.stat small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.stat strong {
  font-size: 24px;
  letter-spacing: -0.04em;
}

.section {
  display: grid;
  gap: 12px;
}

.section h3 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.list {
  display: grid;
  gap: 10px;
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.title-row {
  margin-bottom: 8px;
}

.title-row strong {
  font-size: 15px;
}

.title-row span,
.meta-row span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.empty,
.empty-inline {
  display: grid;
  place-items: center;
  min-height: 180px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

.empty-inline {
  min-height: 120px;
}

@media (max-width: 720px) {
  .topline {
    grid-template-columns: 1fr;
  }
}
</style>
