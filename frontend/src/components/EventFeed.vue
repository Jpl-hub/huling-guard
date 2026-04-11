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
  gap: 16px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
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

.head span:last-child {
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
}

.list {
  display: grid;
  gap: 14px;
}

.event-item {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.event-marker {
  width: 12px;
  height: 12px;
  margin-top: 8px;
  border-radius: 999px;
  background: #43d7ff;
  box-shadow: 0 0 0 6px rgba(67, 215, 255, 0.08);
}

.event-copy {
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(120, 146, 176, 0.12);
}

.title-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  align-items: center;
}

.title-row strong {
  font-size: 16px;
  letter-spacing: -0.02em;
}

.action-pill {
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.12);
  color: #d9f7ff;
  font-size: 12px;
  font-weight: 700;
}

.event-copy p {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.6;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 160px;
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}
</style>
