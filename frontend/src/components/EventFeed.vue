<script setup lang="ts">
import type { Incident } from '../types/runtime'
import { formatRisk, formatTimestamp, incidentLabel, stateLabel } from '../utils/presenters'

import type { ViewMode } from '../types/runtime'

defineProps<{
  incidents: ReadonlyArray<Incident>
  viewMode: ViewMode
}>()
</script>

<template>
  <section class="event-feed">
    <header class="head">
      <h2>最近事件</h2>
      <span>{{ incidents.length ? `${incidents.length} 条` : '无事件' }}</span>
    </header>

    <div v-if="incidents.length" class="list">
      <article
        v-for="incident in incidents"
        :key="`${incident.kind}-${incident.timestamp}`"
        class="event-item"
      >
        <div class="title-row">
          <strong>{{ incidentLabel(incident.kind) }}</strong>
          <span>{{ formatTimestamp(incident.timestamp) }}</span>
        </div>
        <div class="meta-row">
          <span>{{ formatTimestamp(incident.timestamp) }}</span>
          <span v-if="incident.payload?.predicted_state">
            对应状态 {{ stateLabel(String(incident.payload.predicted_state) as any) }}
          </span>
          <span v-if="viewMode === 'xray'">置信度 {{ formatRisk(incident.confidence) }}</span>
        </div>
      </article>
    </div>
    <div v-else class="empty">
      当前没有需要处理的正式事件。
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

.head h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.head span {
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
  margin-bottom: 8px;
}

.title-row strong {
  font-size: 16px;
  letter-spacing: -0.02em;
}

.title-row span,
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
