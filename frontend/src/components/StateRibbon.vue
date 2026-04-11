<script setup lang="ts">
import { computed } from 'vue'

import type { Incident, SessionReport } from '../types/runtime'
import { formatSeconds, formatTimestamp, incidentLabel, stateLabel } from '../utils/presenters'

const props = defineProps<{
  report: Readonly<SessionReport> | null
  incidents: ReadonlyArray<Incident>
}>()

const totalDuration = computed(() => Math.max(props.report?.duration_seconds ?? 0, 0.001))

const ribbonSegments = computed(() =>
  (props.report?.state_segments ?? []).map((segment) => ({
    key: `${segment.state}-${segment.start_timestamp}`,
    label: stateLabel(segment.state),
    state: segment.state,
    widthPercent: Math.max(2, (segment.duration_seconds / totalDuration.value) * 100),
    duration: formatSeconds(segment.duration_seconds),
  })),
)

const markers = computed(() =>
  props.incidents
    .filter((incident) => Number.isFinite(incident.timestamp))
    .slice(0, 8)
    .map((incident) => ({
      key: `${incident.kind}-${incident.timestamp}`,
      label: incidentLabel(incident.kind),
      at: Math.min(100, Math.max(0, (incident.timestamp / totalDuration.value) * 100)),
      timestamp: formatTimestamp(incident.timestamp),
    })),
)
</script>

<template>
  <section class="ribbon-panel">
    <header class="head">
      <div>
        <h2>过程回看</h2>
        <p>用一条连续色带看懂这段过程里状态是怎么变化的。</p>
      </div>
      <span v-if="report" class="duration-chip">全程 {{ formatSeconds(report.duration_seconds) }}</span>
    </header>

    <div v-if="ribbonSegments.length" class="ribbon-shell">
      <div class="ribbon-track">
        <div
          v-for="segment in ribbonSegments"
          :key="segment.key"
          class="segment"
          :data-state="segment.state"
          :style="{ width: `${segment.widthPercent}%` }"
          :title="`${segment.label} · ${segment.duration}`"
        />
        <div
          v-for="marker in markers"
          :key="marker.key"
          class="marker"
          :style="{ left: `${marker.at}%` }"
          :title="`${marker.label} · ${marker.timestamp}`"
        />
      </div>

      <div class="legend">
        <span data-state="normal">正常活动</span>
        <span data-state="near_fall">高风险失衡</span>
        <span data-state="fall">跌倒</span>
        <span data-state="recovery">恢复起身</span>
        <span data-state="prolonged_lying">长时间卧倒</span>
      </div>
    </div>
    <div v-else class="empty">
      当前还没有足够的状态片段可供回看。
    </div>
  </section>
</template>

<style scoped>
.ribbon-panel {
  display: grid;
  gap: 16px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.head p {
  margin: 0;
  color: rgba(201, 217, 235, 0.72);
  font-size: 13px;
  line-height: 1.55;
}

.duration-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(236, 243, 250, 0.88);
  font-size: 12px;
  font-weight: 700;
}

.ribbon-shell {
  display: grid;
  gap: 14px;
}

.ribbon-track {
  position: relative;
  display: flex;
  gap: 4px;
  min-height: 72px;
  padding: 16px 0;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.03);
  overflow: hidden;
}

.segment {
  min-width: 10px;
  height: 40px;
  border-radius: 14px;
  opacity: 0.95;
}

.segment[data-state='normal'] {
  background: #19c37d;
}

.segment[data-state='near_fall'] {
  background: #f3b94d;
}

.segment[data-state='fall'] {
  background: #ff6d77;
}

.segment[data-state='recovery'] {
  background: #49b6ff;
}

.segment[data-state='prolonged_lying'] {
  background: #ff8f66;
}

.marker {
  position: absolute;
  top: 8px;
  width: 2px;
  height: 56px;
  background: rgba(245, 249, 255, 0.95);
  box-shadow: 0 0 0 4px rgba(245, 249, 255, 0.08);
  transform: translateX(-50%);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.legend span {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  color: rgba(207, 221, 237, 0.78);
  font-size: 12px;
}

.legend span::before {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.3);
}

.legend span[data-state='normal']::before {
  background: #19c37d;
}

.legend span[data-state='near_fall']::before {
  background: #f3b94d;
}

.legend span[data-state='fall']::before {
  background: #ff6d77;
}

.legend span[data-state='recovery']::before {
  background: #49b6ff;
}

.legend span[data-state='prolonged_lying']::before {
  background: #ff8f66;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 220px;
  border-radius: 24px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}
</style>
