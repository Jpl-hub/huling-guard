<script setup lang="ts">
import { computed } from 'vue'

import ArchivePreviewCard from '../components/ArchivePreviewCard.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import type { GuardState } from '../types/runtime'
import { matchDemoVideo } from '../utils/media'
import { archiveDisplayName, formatArchiveTime, formatRisk, formatSeconds, stateLabel } from '../utils/presenters'

const store = useRuntimeStore()

const stateFilterDefs = [
  { value: 'fall', label: '跌倒' },
  { value: 'prolonged_lying', label: '长卧风险' },
  { value: 'near_fall', label: '失衡风险' },
  { value: 'recovery', label: '恢复起身' },
  { value: 'normal', label: '正常活动' },
  { value: 'unknown', label: '未稳定判断' },
]

const stateFilterOptions = computed(() => {
  const counts = store.state.archiveSummary?.dominant_state_counts ?? {}
  const activeItems = stateFilterDefs
    .map((item) => ({ ...item, count: Number(counts[item.value] ?? 0) }))
    .filter((item) => item.count > 0)
  const knownValues = new Set(stateFilterDefs.map((item) => item.value))
  const extraItems = Object.entries(counts)
    .filter(([value, count]) => !knownValues.has(value) && Number(count) > 0)
    .map(([value, count]) => ({ value, label: stateLabel(value as GuardState), count: Number(count) }))
  const items = [{ value: '', label: '全部状态', count: Number(store.state.archiveSummary?.archive_total ?? 0) }, ...activeItems, ...extraItems]
  return items.map((item) => ({
    ...item,
    text: `${item.label}（${item.count}）`,
  }))
})

const overviewCards = computed(() => [
  {
    label: '已留档过程',
    value: String(store.state.archiveSummary?.archive_total ?? 0),
    detail: '可回看的完整过程',
  },
  {
    label: '建议先复核',
    value: String(store.state.archiveSummary?.sessions_with_incidents ?? 0),
    detail: '包含正式提醒',
  },
  {
    label: '当前选中',
    value: stateLabel(store.state.selectedArchiveReport?.dominant_state ?? store.state.archiveSummary?.latest_archive?.dominant_state ?? null),
    detail: store.state.selectedArchiveReport
      ? `本段时长 ${formatSeconds(store.state.selectedArchiveReport.duration_seconds)}`
      : formatArchiveTime(store.state.archiveSummary?.latest_archive?.archived_at ?? null),
  },
])

const selectedGuide = computed(() => {
  const report = store.state.selectedArchiveReport
  if (!report) {
    return {
      title: '选择一段过程',
      detail: '左侧选中后立即回放。',
    }
  }
  if (report.incident_total > 0) {
    return {
      title: report.peak_risk ? '先看最高风险时刻' : '先看最近一次提醒',
      detail: '再切到状态切片和风险页签复核。',
    }
  }
  return {
    title: '这段过程没有正式提醒',
    detail: '可作为正常活动对照。',
  }
})

const archiveEntries = computed(() =>
  (store.state.archives?.items ?? []).map((item) => {
    const demoVideo = matchDemoVideo(store.state.demoVideos, [item.session_name, item.session_id])
    return {
      item,
      demoVideo,
      title: archiveDisplayName(
        item.session_name,
        item.archived_at,
        demoVideo?.original_name || demoVideo?.name || null,
      ),
    }
  }),
)

const emptyStateText = computed(() => {
  const selected = stateFilterOptions.value.find((item) => item.value === store.state.archiveFilterState)
  if (!(store.state.archiveSummary?.archive_total ?? 0)) {
    return '暂无历史记录。请先在实时值守页保存当前过程。'
  }
  if (store.state.archiveFilterState) {
    if ((selected?.count ?? 0) <= 0) {
      return `这里还没有“${selected?.label || '该状态'}”记录。`
    }
    return `没有可显示的“${selected?.label || '该状态'}”记录。`
  }
  if (store.state.archiveIncidentsOnly) {
    return '当前没有带提醒的记录。'
  }
  return '没有可展示的回看记录。'
})

function handleDeleteArchive(sessionId: string) {
  if (!window.confirm("确定要删除这条历史留档吗？")) {
    return
  }
  void store.deleteArchive(sessionId)
}

</script>

<template>
  <section class="records-page">
    <section class="overview-band">
      <div class="overview-copy">
        <h2>历史回看</h2>
      </div>

      <div class="overview-stats">
        <article v-for="item in overviewCards" :key="item.label" class="overview-item">
          <small>{{ item.label }}</small>
          <strong>{{ item.value }}</strong>
          <span>{{ item.detail }}</span>
        </article>
      </div>
    </section>

    <section class="records-layout">
      <section class="records-list">
        <header class="records-head">
          <div>
            <h2>已保存过程</h2>
          </div>
          <div class="filters">
            <a-select
              :model-value="store.state.archiveFilterState"
              size="large"
              placeholder="全部状态"
              @change="store.setArchiveFilterState(String($event))"
            >
              <a-option
                v-for="option in stateFilterOptions"
                :key="option.value || 'all'"
                :value="option.value"
              >
                {{ option.text }}
              </a-option>
            </a-select>
            <label class="switch-line">
              <span>只看提醒</span>
              <a-switch
                :model-value="store.state.archiveIncidentsOnly"
                @change="store.setArchiveIncidentsOnly(Boolean($event))"
              />
            </label>
          </div>
        </header>

        <transition-group name="stack-fade" tag="div" class="archive-list">
          <article
            v-for="entry in archiveEntries"
            :key="entry.item.session_id"
            class="archive-item"
            :class="{ active: entry.item.session_id === store.state.selectedArchiveId }"
            role="button"
            tabindex="0"
            :aria-pressed="entry.item.session_id === store.state.selectedArchiveId"
            @click="store.loadArchive(entry.item.session_id)"
            @keydown.enter.prevent="store.loadArchive(entry.item.session_id)"
            @keydown.space.prevent="store.loadArchive(entry.item.session_id)"
          >
            <div class="archive-row">
              <div v-if="entry.demoVideo?.poster_url" class="archive-thumb">
                <img :src="entry.demoVideo.poster_url" :alt="entry.item.session_name || entry.item.session_id" />
              </div>
              <div class="archive-body">
                <div class="title-row">
                  <div>
                    <strong>{{ entry.title }}</strong>
                    <p>{{ formatArchiveTime(entry.item.archived_at) }}</p>
                  </div>
                  <div class="archive-actions">
                    <span class="state-pill">{{ stateLabel(entry.item.dominant_state) }}</span>
                    <button
                      type="button"
                      class="archive-delete"
                      @click.stop="handleDeleteArchive(entry.item.session_id)"
                    >
                      删除留档
                    </button>
                  </div>
                </div>
                <div class="meta-row">
                  <span>时长 {{ formatSeconds(entry.item.duration_seconds) }}</span>
                  <span>{{ entry.item.incident_total > 0 ? `提醒 ${entry.item.incident_total} 次` : '没有正式提醒' }}</span>
                  <span>峰值 {{ formatRisk(entry.item.peak_risk_score) }}</span>
                </div>
              </div>
            </div>
          </article>
          <div v-if="!(store.state.archives?.items?.length)" class="empty">
            <a-empty>
              <template #description>
                <span>{{ emptyStateText }}</span>
              </template>
            </a-empty>
          </div>
        </transition-group>
      </section>

      <section class="preview-panel">
        <div class="preview-guide">
          <strong>{{ selectedGuide.title }}</strong>
          <span>{{ selectedGuide.detail }}</span>
        </div>
        <ArchivePreviewCard
          :report="store.state.selectedArchiveReport"
          :demo-videos="store.state.demoVideos"
        />
      </section>
    </section>
  </section>
</template>

<style scoped>
.records-page {
  display: grid;
  gap: var(--space-5);
}

.overview-band {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-3) 2px var(--space-1);
}

.overview-copy {
  display: block;
}

.overview-copy h2 {
  margin: 0;
  font-size: 34px;
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.records-list,
.preview-panel {
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.overview-item {
  padding: 2px 0 2px var(--space-4);
  border-left: 1px solid var(--color-line-strong);
}

.overview-item small {
  display: block;
  margin-bottom: 10px;
  color: var(--color-text-muted);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.overview-item strong {
  display: block;
  margin-bottom: 6px;
  font-size: 28px;
  letter-spacing: -0.05em;
}

.overview-item span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.records-layout {
  display: grid;
  grid-template-columns: minmax(340px, 0.82fr) minmax(0, 1.18fr);
  gap: var(--space-5);
  align-items: start;
}

.records-list,
.preview-panel {
  padding: var(--space-6);
}

.records-list {
  position: sticky;
  top: 96px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: calc(100vh - 140px);
  max-height: calc(100vh - 140px);
  min-height: 560px;
}

.preview-panel {
  display: grid;
  gap: var(--space-4);
  align-self: start;
}

.preview-guide {
  display: grid;
  gap: 6px;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-line-soft);
}

.preview-guide strong {
  font-size: 16px;
  letter-spacing: -0.02em;
}

.preview-guide span {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.records-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  align-items: flex-start;
  margin-bottom: var(--space-5);
}

.records-head h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.filters {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
}

.switch-line {
  display: inline-flex;
  gap: 10px;
  align-items: center;
  color: var(--color-text-primary);
  font-size: 13px;
}

.archive-list {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: var(--space-2);
  overscroll-behavior: contain;
}

.archive-item {
  position: relative;
  display: grid;
  gap: 10px;
  text-align: left;
  padding: 18px 18px 18px 22px;
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  color: inherit;
  cursor: pointer;
  transition: transform 180ms ease, background-color 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
}

.archive-item::before {
  content: '';
  position: absolute;
  inset: 16px auto 16px 10px;
  width: 3px;
  border-radius: 999px;
  background: var(--color-accent-soft);
}

.archive-item:hover,
.archive-item.active {
  transform: translateY(-2px);
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1px var(--color-accent);
}

.archive-item.active::before {
  background: var(--color-accent);
}

.archive-item:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px var(--color-accent), 0 0 0 2px rgba(121, 212, 231, 0.14);
}

.stack-fade-enter-active,
.stack-fade-leave-active,
.stack-fade-move {
  transition: transform 220ms ease, opacity 220ms ease;
}

.stack-fade-enter-from,
.stack-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.stack-fade-leave-active {
  pointer-events: none;
}


.archive-delete {
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  border: 0;
  background: var(--color-alert-soft);
  color: var(--color-text-alert);
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 180ms ease, color 180ms ease;
}

.archive-delete:hover {
  background: rgba(255, 140, 144, 0.22);
  color: var(--color-text-primary);
}

.archive-row {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: center;
}

.archive-thumb {
  overflow: hidden;
  border-radius: 18px;
  background: var(--color-bg-strong);
  aspect-ratio: 16 / 10;
}

.archive-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.archive-body {
  display: grid;
  gap: var(--space-3);
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.archive-actions {
  display: inline-flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}

.title-row strong {
  display: block;
  margin-bottom: 6px;
  font-size: 16px;
}

.title-row p {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.state-pill {
  padding: 9px 12px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 700;
}

.meta-row span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 240px;
  padding: var(--space-5) 0;
  color: var(--color-text-tertiary);
  text-align: center;
}

.empty :deep(.arco-empty-icon) {
  opacity: 0.72;
}

.empty :deep(.arco-empty-description) {
  color: var(--color-text-tertiary);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1200px) {
  .records-layout,
  .overview-stats {
    grid-template-columns: 1fr;
  }

  .records-list {
    position: static;
    height: auto;
    max-height: none;
    min-height: 0;
  }

  .archive-list {
    max-height: 70vh;
  }
}

@media (max-width: 720px) {
  .overview-band,
  .records-list,
  .preview-panel {
    padding: var(--space-4);
    border-radius: var(--radius-sm);
  }

  .records-head {
    flex-direction: column;
  }

  .archive-row {
    grid-template-columns: 1fr;
  }
}
</style>
