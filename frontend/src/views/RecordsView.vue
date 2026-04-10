<script setup lang="ts">
import ArchivePreviewCard from '../components/ArchivePreviewCard.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatArchiveTime, formatRisk, formatSeconds, stateLabel } from '../utils/presenters'

const store = useRuntimeStore()
</script>

<template>
  <section class="records-page">
    <section class="summary-strip">
      <article class="summary-block">
        <small>回看总数</small>
        <strong>{{ store.state.archiveSummary?.archive_total ?? 0 }}</strong>
      </article>
      <article class="summary-block">
        <small>包含提醒</small>
        <strong>{{ store.state.archiveSummary?.sessions_with_incidents ?? 0 }}</strong>
      </article>
      <article class="summary-block">
        <small>平均时长</small>
        <strong>{{ formatSeconds(store.state.archiveSummary?.mean_duration_seconds ?? 0) }}</strong>
      </article>
      <article class="summary-block emphasis">
        <small>最近一条</small>
        <strong>{{ stateLabel(store.state.archiveSummary?.latest_archive?.dominant_state ?? null) }}</strong>
        <span>{{ formatArchiveTime(store.state.archiveSummary?.latest_archive?.archived_at ?? null) }}</span>
      </article>
    </section>

    <section class="records-layout">
      <section class="records-list">
        <header class="records-head">
          <div>
            <span class="section-kicker">Archive</span>
            <h2>回看记录</h2>
          </div>
          <div class="filters">
            <a-select
              :model-value="store.state.archiveFilterState"
              size="large"
              placeholder="全部状态"
              @change="store.setArchiveFilterState(String($event))"
            >
              <a-option value="">全部状态</a-option>
              <a-option value="normal">正常活动</a-option>
              <a-option value="near_fall">高风险失衡</a-option>
              <a-option value="fall">跌倒</a-option>
              <a-option value="recovery">恢复起身</a-option>
              <a-option value="prolonged_lying">长时间卧倒</a-option>
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

        <div class="archive-list">
          <button
            v-for="item in store.state.archives?.items ?? []"
            :key="item.session_id"
            type="button"
            class="archive-item"
            :class="{ active: item.session_id === store.state.selectedArchiveId }"
            @click="store.loadArchive(item.session_id)"
          >
            <div class="title-row">
              <strong>{{ item.session_name || item.session_id }}</strong>
              <span>{{ stateLabel(item.dominant_state) }}</span>
            </div>
            <div class="meta-row">
              <span>{{ formatArchiveTime(item.archived_at) }}</span>
              <span>{{ formatSeconds(item.duration_seconds) }}</span>
            </div>
            <div class="meta-row muted">
              <span>事件 {{ item.incident_total }}</span>
              <span>峰值 {{ formatRisk(item.peak_risk_score) }}</span>
            </div>
          </button>
          <div v-if="!(store.state.archives?.items?.length)" class="empty">
            当前筛选条件下没有可展示的回看记录。
          </div>
        </div>
      </section>

      <section class="preview-panel">
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
  gap: 20px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-block,
.records-list,
.preview-panel {
  border-radius: 28px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.summary-block {
  padding: 18px 20px;
}

.summary-block small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.summary-block strong {
  display: block;
  margin-bottom: 6px;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.summary-block span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.summary-block.emphasis {
  background: linear-gradient(180deg, rgba(67, 215, 255, 0.1), rgba(6, 14, 24, 0.82));
}

.records-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.84fr) minmax(0, 1.16fr);
  gap: 18px;
}

.records-list,
.preview-panel {
  padding: 22px;
}

.records-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  margin-bottom: 18px;
}

.section-kicker {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(143, 181, 221, 0.76);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.records-head h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.filters {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.switch-line {
  display: inline-flex;
  gap: 10px;
  align-items: center;
  color: rgba(225, 235, 246, 0.84);
  font-size: 13px;
}

.archive-list {
  display: grid;
  gap: 12px;
}

.archive-item {
  position: relative;
  display: grid;
  gap: 8px;
  text-align: left;
  padding: 16px 18px 16px 22px;
  border-radius: 24px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
  color: inherit;
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, background-color 180ms ease;
}

.archive-item::before {
  content: '';
  position: absolute;
  inset: 16px auto 16px 10px;
  width: 3px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.16);
}

.archive-item:hover,
.archive-item.active {
  transform: translateY(-2px);
  border-color: rgba(67, 215, 255, 0.22);
  background: rgba(67, 215, 255, 0.08);
}

.archive-item.active::before {
  background: #43d7ff;
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.title-row strong {
  font-size: 15px;
}

.title-row span,
.meta-row span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.meta-row.muted span {
  color: rgba(199, 214, 231, 0.58);
}

.empty {
  display: grid;
  place-items: center;
  min-height: 180px;
  border-radius: 24px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 1200px) {
  .records-layout,
  .summary-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .records-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
