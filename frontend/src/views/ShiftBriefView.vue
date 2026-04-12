<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'

import { runtimeApi } from '../services/runtimeApi'
import type { ArchiveRecord, ArchiveSummaryResponse, GuardState } from '../types/runtime'
import { archiveDisplayName, formatArchiveTime, formatRisk, formatSeconds, stateLabel } from '../utils/presenters'

const loading = ref(true)
const records = ref<ArchiveRecord[]>([])
const summary = ref<ArchiveSummaryResponse | null>(null)
const mode = ref<'all' | 'incidents'>('all')

async function loadBrief(): Promise<void> {
  loading.value = true
  try {
    const [archivesPayload, summaryPayload] = await Promise.all([
      runtimeApi.archives({ limit: 200 }),
      runtimeApi.archiveSummary(),
    ])
    records.value = archivesPayload.items
    summary.value = summaryPayload
  } catch (error) {
    const message = error instanceof Error ? error.message : '交接班数据加载失败'
    Message.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadBrief()
})

const visibleRecords = computed(() =>
  mode.value === 'incidents'
    ? records.value.filter((item) => Number(item.incident_total ?? 0) > 0)
    : records.value,
)

const sortedByRisk = computed(() =>
  [...visibleRecords.value].sort((a, b) => Number(b.peak_risk_score ?? 0) - Number(a.peak_risk_score ?? 0)),
)

const priorityRecords = computed(() =>
  sortedByRisk.value.filter((item) => Number(item.incident_total ?? 0) > 0 || Number(item.peak_risk_score ?? 0) >= 0.55).slice(0, 6),
)

const stateCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const item of visibleRecords.value) {
    const key = String(item.dominant_state ?? 'unknown')
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([state, count]) => ({ state, count, label: stateLabel(state as GuardState) }))
    .sort((a, b) => b.count - a.count)
})

const maxStateCount = computed(() => Math.max(...stateCounts.value.map((item) => item.count), 1))
const totalDuration = computed(() => visibleRecords.value.reduce((sum, item) => sum + Number(item.duration_seconds ?? 0), 0))
const incidentRecordCount = computed(() => visibleRecords.value.filter((item) => Number(item.incident_total ?? 0) > 0).length)
const incidentCount = computed(() => visibleRecords.value.reduce((sum, item) => sum + Number(item.incident_total ?? 0), 0))
const maxRisk = computed(() => Math.max(...visibleRecords.value.map((item) => Number(item.peak_risk_score ?? 0)), 0))
const dominantStateLabel = computed(() => stateCounts.value[0]?.label ?? '暂无记录')
const latestRecord = computed(() => visibleRecords.value[0] ?? null)

const summaryCards = computed(() => [
  { label: '纳入留档', value: String(visibleRecords.value.length), detail: mode.value === 'incidents' ? '仅含提醒记录' : '全部保存过程' },
  { label: '正式提醒', value: String(incidentCount.value), detail: `${incidentRecordCount.value} 段过程包含提醒` },
  { label: '最高风险', value: formatRisk(maxRisk.value), detail: dominantStateLabel.value },
  { label: '过程时长', value: formatSeconds(totalDuration.value), detail: latestRecord.value ? `最近 ${formatArchiveTime(latestRecord.value.archived_at)}` : '暂无留档' },
])

const briefLines = computed(() => {
  if (!visibleRecords.value.length) {
    return ['当前没有可纳入交接的历史留档。']
  }
  const lines = [
    `本次交接纳入 ${visibleRecords.value.length} 段留档，累计过程时长 ${formatSeconds(totalDuration.value)}。`,
    `共记录 ${incidentCount.value} 次正式提醒，涉及 ${incidentRecordCount.value} 段过程。`,
    `当前主要状态为“${dominantStateLabel.value}”，最高风险值 ${formatRisk(maxRisk.value)}。`,
  ]
  if (priorityRecords.value.length) {
    const first = priorityRecords.value[0]
    lines.push(`建议优先复核：${archiveDisplayName(first.session_name, first.archived_at)}，状态为“${stateLabel(first.dominant_state)}”。`)
  } else {
    lines.push('未发现需要优先复核的正式提醒记录。')
  }
  return lines
})

function fallbackCopy(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  return copied
}

async function copyBrief(): Promise<void> {
  const text = briefLines.value.join('\n')
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else if (!fallbackCopy(text)) {
      throw new Error('copy_failed')
    }
    Message.success('交接班摘要已复制')
  } catch {
    if (fallbackCopy(text)) {
      Message.success('交接班摘要已复制')
      return
    }
    Message.error('复制失败，请手动选择文本')
  }
}
</script>

<template>
  <section class="brief-page">
    <header class="brief-head">
      <div>
        <small class="eyebrow">SHIFT BRIEF</small>
        <h2>交接班简报</h2>
      </div>
      <div class="brief-actions">
        <div class="mode-tabs" role="tablist" aria-label="简报范围">
          <button type="button" :data-active="mode === 'all'" @click="mode = 'all'">全部留档</button>
          <button type="button" :data-active="mode === 'incidents'" @click="mode = 'incidents'">只看提醒</button>
        </div>
        <a-button size="large" :loading="loading" @click="loadBrief">刷新</a-button>
        <a-button size="large" type="primary" :disabled="!visibleRecords.length" @click="copyBrief">复制摘要</a-button>
      </div>
    </header>

    <section class="brief-stats">
      <article v-for="item in summaryCards" :key="item.label">
        <small>{{ item.label }}</small>
        <strong>{{ item.value }}</strong>
        <span>{{ item.detail }}</span>
      </article>
    </section>

    <section v-if="visibleRecords.length" class="brief-layout">
      <section class="brief-paper">
        <header>
          <h3>本次摘要</h3>
          <span>{{ summary?.archive_total ?? records.length }} 条历史留档</span>
        </header>
        <ol>
          <li v-for="line in briefLines" :key="line">{{ line }}</li>
        </ol>
      </section>

      <section class="brief-panel priority-panel">
        <header>
          <h3>重点复核</h3>
          <span>{{ priorityRecords.length ? '按风险排序' : '暂无重点项' }}</span>
        </header>
        <div class="priority-list">
          <article v-for="item in priorityRecords" :key="item.session_id">
            <div>
              <strong>{{ archiveDisplayName(item.session_name, item.archived_at) }}</strong>
              <span>{{ formatArchiveTime(item.archived_at) }}</span>
            </div>
            <div class="priority-meta">
              <span>{{ stateLabel(item.dominant_state) }}</span>
              <span>提醒 {{ item.incident_total }}</span>
              <span>风险 {{ formatRisk(item.peak_risk_score) }}</span>
            </div>
          </article>
          <a-empty v-if="!priorityRecords.length" description="当前没有需要优先复核的留档" />
        </div>
      </section>
    </section>

    <section v-if="visibleRecords.length" class="brief-panel state-panel">
      <header>
        <h3>状态分布</h3>
        <span>{{ mode === 'incidents' ? '提醒记录' : '全部留档' }}</span>
      </header>
      <div class="state-bars">
        <article v-for="item in stateCounts" :key="item.state">
          <div class="state-row">
            <strong>{{ item.label }}</strong>
            <span>{{ item.count }}</span>
          </div>
          <div class="bar-track" aria-hidden="true">
            <span :style="{ width: `${Math.max(8, (item.count / maxStateCount) * 100)}%` }" />
          </div>
        </article>
      </div>
    </section>

    <section v-if="!visibleRecords.length && !loading" class="brief-empty">
      <a-empty description="当前没有可生成简报的历史留档" />
    </section>
  </section>
</template>

<style scoped>
.brief-page {
  display: grid;
  gap: var(--space-6);
}

.brief-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  align-items: end;
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-line-soft);
}

.eyebrow,
.brief-stats small,
.brief-panel header span,
.brief-paper header span {
  color: var(--color-text-tertiary);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.brief-head h2 {
  margin: var(--space-1) 0 0;
  font-size: clamp(30px, 4vw, 48px);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

.brief-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.mode-tabs {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border-radius: 999px;
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.mode-tabs button {
  border: 0;
  border-radius: 999px;
  padding: 9px 13px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  transition: color 160ms ease, background-color 160ms ease, transform 160ms ease;
}

.mode-tabs button:active {
  transform: scale(0.98);
}

.mode-tabs button[data-active='true'] {
  background: rgba(121, 212, 231, 0.12);
  color: var(--color-text-primary);
}

.brief-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.brief-stats article {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-line-soft);
}

.brief-stats strong {
  font-family: var(--font-mono);
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.brief-stats span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.brief-layout {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(360px, 1.05fr);
  gap: var(--space-6);
  align-items: start;
}

.brief-paper,
.brief-panel {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.brief-paper header,
.brief-panel header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: center;
}

.brief-paper h3,
.brief-panel h3 {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.04em;
}

.brief-paper ol {
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding-left: 22px;
  color: var(--color-text-primary);
  line-height: 1.75;
}

.priority-list,
.state-bars {
  display: grid;
  gap: var(--space-3);
}

.priority-list article {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4) 0 0;
  border-top: 1px solid var(--color-line-soft);
}

.priority-list article:first-child {
  padding-top: 0;
  border-top: 0;
}

.priority-list strong {
  display: block;
  margin-bottom: 5px;
  font-size: 15px;
}

.priority-list span,
.priority-meta span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.priority-meta {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.state-bars article {
  display: grid;
  gap: var(--space-2);
}

.state-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: center;
}

.state-row span {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.bar-track {
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.035);
}

.bar-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(121, 212, 231, 0.38), rgba(121, 212, 231, 0.92));
}

.brief-empty {
  display: grid;
  place-items: center;
  min-height: 320px;
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

@media (max-width: 1040px) {
  .brief-head,
  .brief-layout {
    grid-template-columns: 1fr;
  }

  .brief-head {
    display: grid;
    align-items: start;
  }

  .brief-actions {
    justify-content: flex-start;
  }

  .brief-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .brief-stats {
    grid-template-columns: 1fr;
  }

  .brief-actions {
    display: grid;
    width: 100%;
  }

  .mode-tabs,
  .brief-actions :deep(.arco-btn) {
    width: 100%;
  }
}
</style>
