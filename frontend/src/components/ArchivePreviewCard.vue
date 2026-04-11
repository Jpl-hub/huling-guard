<script setup lang="ts">
import { computed, ref } from 'vue'

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

const props = defineProps<{
  report: Readonly<SessionReport> | null
  demoVideos: ReadonlyArray<DemoVideoItem>
}>()

const videoRef = ref<HTMLVideoElement | null>(null)

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

      <div class="lead-copy">
        <strong>{{ report.incident_total > 0 ? '优先查看最高风险时刻。' : '这段过程没有正式提醒。' }}</strong>
      </div>

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

      <div v-if="matchedVideo" class="video-block">
        <div class="video-head">
          <h3>过程回放</h3>
          <span>{{ matchedVideo.original_name || matchedVideo.name }}</span>
        </div>
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
          <div class="jump-row">
            <button
              v-if="report.peak_risk"
              type="button"
              class="jump-chip"
              @click="seekTo(report.peak_risk.timestamp)"
            >
              最高风险时刻 · {{ formatTimestamp(report.peak_risk.timestamp) }}
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

      <div class="section">
        <h3>这段过程发生了什么</h3>
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

      <div class="section two-col">
        <div>
          <h3>高风险时刻</h3>
          <div class="list compact">
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

        <div>
          <h3>系统提醒</h3>
          <div class="list compact">
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
              这条记录没有正式提醒。
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty">
      选择一条回看记录后，这里会显示完整过程和关键时刻。
    </div>
  </section>
</template>

<style scoped>
.preview-card {
  display: grid;
  gap: 22px;
}

.lead-copy {
  display: grid;
  gap: 6px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(120, 146, 176, 0.12);
}

.lead-copy strong {
  font-size: 15px;
}

.lead-copy span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
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

.video-head h3,
.section h3 {
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
  font-size: 24px;
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
  font-size: 12px;
  font-weight: 700;
}

.topline {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat {
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.02);
}

.stat.emphasis {
  background: rgba(67, 215, 255, 0.08);
}

.stat small {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.62);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.stat strong {
  font-size: 22px;
  letter-spacing: -0.04em;
}

.section {
  display: grid;
  gap: 12px;
}

.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.list {
  display: grid;
  gap: 12px;
}

.item {
  padding: 14px 0;
  border-top: 1px solid rgba(120, 146, 176, 0.12);
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

.meta-row span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 12px;
}

.empty,
.empty-inline {
  display: grid;
  place-items: center;
  min-height: 160px;
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 980px) {
  .topline,
  .two-col {
    grid-template-columns: 1fr;
  }
}
</style>
