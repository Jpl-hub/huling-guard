<script setup lang="ts">
import { computed } from 'vue'

import type { DisplayState, Incident, SessionReport } from '../types/runtime'
import { formatRisk, formatTimestamp, incidentAction, incidentLabel, stateLabel } from '../utils/presenters'

import type { ViewMode } from '../types/runtime'

const props = defineProps<{
  incidents: ReadonlyArray<Incident>
  displayState: Readonly<DisplayState>
  report: Readonly<SessionReport> | null
  viewMode: ViewMode
}>()

const helperText = computed(() => {
  if (props.incidents.length) {
    return '需要处理的关键时刻。'
  }
  if (!props.displayState.ready && (props.report?.total_frames ?? 0) > 0) {
    return props.report?.ready_frames
      ? '系统已形成部分连续判断，正在等待正式提醒。'
      : '系统已进入分析，正在建立时序窗口。'
  }
  return '需要处理的关键时刻。'
})

const emptyText = computed(() => {
  if (!props.displayState.ready && (props.report?.total_frames ?? 0) > 0) {
    return props.report?.ready_frames
      ? '已经开始形成连续判断，目前还没有正式提醒。'
      : '已经开始分析这段视频，正在等待第一段连续结论。'
  }
  return '暂无需要处理的变化。'
})
</script>

<template>
  <section class="event-feed">
    <header class="head">
      <div>
        <h2>最近变化</h2>
        <p>{{ helperText }}</p>
      </div>
      <span>{{ incidents.length ? `${incidents.length} 条` : '无提醒' }}</span>
    </header>

    <div v-if="incidents.length" class="list">
      <article
        v-for="incident in incidents"
        :key="`${incident.kind}-${incident.timestamp}`"
        class="event-item"
      >
        <span class="event-marker" />
        <div class="event-copy">
          <div class="title-row">
            <strong>{{ incidentLabel(incident.kind) }}</strong>
            <span class="action-pill">{{ incidentAction(incident.kind) }}</span>
          </div>
          <p>
            {{ formatTimestamp(incident.timestamp) }}
            <template v-if="incident.payload?.predicted_state">
              · 当前判断 {{ stateLabel(String(incident.payload.predicted_state) as any) }}
            </template>
            <template v-if="viewMode === 'xray'">
              · 置信度 {{ formatRisk(incident.confidence) }}
            </template>
          </p>
        </div>
      </article>
    </div>
    <div v-else class="empty">
      {{ emptyText }}
    </div>
  </section>
</template>

<style scoped>
.event-feed {
  display: grid;
  gap: var(--space-4);
}

.head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: flex-start;
}

.head h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.03em;
}

.head p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.head span:last-child {
  color: var(--color-text-tertiary);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.list {
  display: grid;
  gap: var(--space-4);
}

.event-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
}

.event-marker {
  width: 10px;
  height: 10px;
  margin-top: 9px;
  border-radius: 999px;
  background: var(--color-accent);
  box-shadow: 0 0 0 5px var(--color-accent-soft);
}

.event-copy {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-line-soft);
}

.title-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
  align-items: center;
}

.title-row strong {
  font-size: 15px;
  letter-spacing: -0.02em;
}

.action-pill {
  color: var(--color-text-tertiary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.event-copy p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 140px;
  color: var(--color-text-tertiary);
  text-align: center;
}
</style>
