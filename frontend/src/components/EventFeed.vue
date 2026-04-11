<script setup lang="ts">
import type { Incident } from '../types/runtime'
import { formatRisk, formatTimestamp, incidentAction, incidentLabel, stateLabel } from '../utils/presenters'

import type { ViewMode } from '../types/runtime'

defineProps<{
  incidents: ReadonlyArray<Incident>
  viewMode: ViewMode
}>()
</script>

<template>
  <section class="event-feed">
    <header class="head">
      <div>
        <h2>最近变化</h2>
        <p>需要处理的关键时刻。</p>
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
      暂无需要处理的变化。
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
