<script setup lang="ts">
import { computed } from 'vue'

import type { DisplayState, SessionReport, ViewMode } from '../types/runtime'
import { formatSeconds, formatTimestamp, stateLabel } from '../utils/presenters'

const props = defineProps<{
  report: Readonly<SessionReport> | null
  displayState: Readonly<DisplayState>
  runtimeChips: ReadonlyArray<string>
  viewMode: ViewMode
}>()

const dominantStateText = computed(() =>
  props.displayState.ready
    ? stateLabel(props.report?.dominant_state ?? props.displayState.predictedState)
    : props.report?.ready_frames
      ? '正在形成结论'
      : '时序预热中',
)

const peakMomentText = computed(() => {
  if (props.report?.peak_risk?.timestamp != null) {
    return formatTimestamp(props.report.peak_risk.timestamp)
  }
  return props.displayState.ready ? '-' : '尚未形成'
})

const durationText = computed(() => {
  if (props.displayState.ready || (props.report?.duration_seconds ?? 0) > 0) {
    return formatSeconds(props.report?.duration_seconds ?? 0)
  }
  if ((props.report?.total_frames ?? 0) > 0) {
    return `已分析 ${props.report?.total_frames ?? 0} 帧`
  }
  return '-'
})

const emptyText = computed(() => {
  if (!props.report) {
    return '当前还没有可展示的过程片段。'
  }
  if (!props.displayState.ready) {
    if (props.report.ready_frames > 0) {
      return `已形成 ${props.report.ready_frames} 帧连续判断，正在等待更稳定的过程片段。`
    }
    if (props.report.total_frames > 0) {
      return `已读取 ${props.report.total_frames} 帧，正在建立连续时序窗口。`
    }
  }
  return '还没有形成稳定过程片段。'
})
</script>

<template>
  <section class="session-panel">
    <header class="head">
      <div>
        <h2>这段过程</h2>
        <p>状态持续与风险高点。</p>
      </div>
    </header>

    <dl class="summary-strip">
      <div>
        <dt>主导状态</dt>
        <dd>{{ dominantStateText }}</dd>
      </div>
      <div>
        <dt>最高风险时刻</dt>
        <dd>{{ peakMomentText }}</dd>
      </div>
      <div>
        <dt>本段时长</dt>
        <dd>{{ durationText }}</dd>
      </div>
    </dl>

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
        </div>
      </article>
      <div v-if="!(report?.longest_segments?.length)" class="empty">
        {{ emptyText }}
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

.head h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.head p {
  margin: 8px 0 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 13px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}

.summary-strip div {
  padding-top: 14px;
  border-top: 1px solid rgba(120, 146, 176, 0.12);
}

.summary-strip dt {
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
}

.summary-strip dd {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.04;
  letter-spacing: -0.04em;
}

.segments {
  display: grid;
  gap: 12px;
}

.segment-item {
  padding: 14px 0;
  border-top: 1px solid rgba(120, 146, 176, 0.12);
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
  background: rgba(255, 255, 255, 0.03);
  color: rgba(225, 235, 246, 0.84);
  font-size: 13px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 140px;
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 720px) {
  .summary-strip {
    grid-template-columns: 1fr;
  }
}
</style>
