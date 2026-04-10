<script setup lang="ts">
import type { DisplayState, SessionReport, ViewMode } from '../types/runtime'
import { formatSeconds, formatTimestamp, stateLabel } from '../utils/presenters'

defineProps<{
  report: Readonly<SessionReport> | null
  displayState: Readonly<DisplayState>
  runtimeChips: ReadonlyArray<string>
  viewMode: ViewMode
}>()
</script>

<template>
  <section class="session-panel">
    <header class="head">
      <div>
        <span class="section-kicker">Session</span>
        <h2>本段过程</h2>
      </div>
    </header>

    <div class="summary-grid">
      <article class="summary-box">
        <small>主导状态</small>
        <strong>{{ stateLabel(report?.dominant_state ?? displayState.predictedState) }}</strong>
      </article>
      <article class="summary-box">
        <small>最高风险时刻</small>
        <strong>{{ formatTimestamp(report?.peak_risk?.timestamp ?? null) }}</strong>
      </article>
      <article class="summary-box">
        <small>本段时长</small>
        <strong>{{ formatSeconds(report?.duration_seconds ?? 0) }}</strong>
      </article>
    </div>

    <div class="segments">
      <article
        v-for="segment in (report?.longest_segments ?? []).slice(0, 4)"
        :key="`${segment.state}-${segment.start_timestamp}`"
        class="segment-item"
      >
        <div class="segment-title">
          <strong>{{ stateLabel(segment.state) }}</strong>
          <span>{{ formatSeconds(segment.duration_seconds) }}</span>
        </div>
        <div class="segment-meta">
          <span>开始 {{ formatTimestamp(segment.start_timestamp) }}</span>
          <span>结束 {{ formatTimestamp(segment.end_timestamp) }}</span>
          <span>共持续 {{ formatSeconds(segment.duration_seconds) }}</span>
        </div>
      </article>
      <div v-if="!(report?.longest_segments?.length)" class="empty">
        当前还没有足够稳定的过程片段可以展示。
      </div>
    </div>

    <div v-if="viewMode === 'xray'" class="chips">
      <span v-for="chip in runtimeChips" :key="chip" class="chip">{{ chip }}</span>
    </div>
  </section>
</template>

<style scoped>
.session-panel {
  display: grid;
  gap: 18px;
}

.section-kicker {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(143, 181, 221, 0.76);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.head h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.summary-box {
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
}

.summary-box small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-box strong {
  font-size: 26px;
  line-height: 1.04;
  letter-spacing: -0.04em;
}

.segments {
  display: grid;
  gap: 12px;
}

.segment-item {
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
}

.segment-title,
.segment-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.segment-title {
  margin-bottom: 8px;
}

.segment-title strong {
  font-size: 16px;
}

.segment-title span,
.segment-meta span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chip {
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid rgba(120, 146, 176, 0.18);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(225, 235, 246, 0.84);
  font-size: 13px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 140px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 720px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
