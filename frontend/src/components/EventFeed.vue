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
        <span class="section-kicker">Recent events</span>
        <h2>最近提醒</h2>
      </div>
      <span>{{ incidents.length ? `${incidents.length} 条` : '无提醒' }}</span>
    </header>

    <div v-if="incidents.length" class="list">
      <article
        v-for="incident in incidents"
        :key="`${incident.kind}-${incident.timestamp}`"
        class="event-item"
      >
        <div class="title-row">
          <strong>{{ incidentLabel(incident.kind) }}</strong>
          <span class="action-pill">{{ incidentAction(incident.kind) }}</span>
        </div>
        <div class="meta-row">
          <span>{{ formatTimestamp(incident.timestamp) }}</span>
          <span v-if="incident.payload?.predicted_state">
            状态 {{ stateLabel(String(incident.payload.predicted_state) as any) }}
          </span>
          <span v-if="viewMode === 'xray'">置信度 {{ formatRisk(incident.confidence) }}</span>
        </div>
      </article>
    </div>
    <div v-else class="empty">
      当前没有需要处理的提醒。
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
  align-items: baseline;
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

.head span:last-child {
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
}

.list {
  display: grid;
  gap: 12px;
}

.event-item {
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.title-row {
  margin-bottom: 10px;
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

.meta-row span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 160px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}
</style>
