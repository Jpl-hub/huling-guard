<script setup lang="ts">
import ArchivePreviewCard from '../components/ArchivePreviewCard.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatArchiveTime, formatRisk, formatSeconds, stateLabel } from '../utils/presenters'

const store = useRuntimeStore()
</script>

<template>
  <section class="records-page">
    <div class="summary-strip">
      <article class="summary-card">
        <small>记录总数</small>
        <strong>{{ store.state.archiveSummary?.archive_total ?? 0 }}</strong>
        <span>已保存过程</span>
      </article>
      <article class="summary-card">
        <small>重点记录</small>
        <strong>{{ store.state.archiveSummary?.sessions_with_incidents ?? 0 }}</strong>
        <span>包含关键事件</span>
      </article>
      <article class="summary-card">
        <small>平均时长</small>
        <strong>{{ formatSeconds(store.state.archiveSummary?.mean_duration_seconds ?? 0) }}</strong>
        <span>单条过程平均时长</span>
      </article>
      <article class="summary-card emphasis">
        <small>最近归档</small>
        <strong>{{ stateLabel(store.state.archiveSummary?.latest_archive?.dominant_state ?? null) }}</strong>
        <span>{{ formatArchiveTime(store.state.archiveSummary?.latest_archive?.archived_at ?? null) }}</span>
      </article>
    </div>

    <section class="records-layout">
      <div class="records-list panel">
        <header class="head">
          <div>
            <h2>历史回看</h2>
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
              <span>只看有事件</span>
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
              <span>事件 {{ item.incident_total }}</span>
              <span>峰值 {{ formatRisk(item.peak_risk_score) }}</span>
            </div>
          </button>
          <div v-if="!(store.state.archives?.items?.length)" class="empty">
            当前筛选条件下没有可展示的历史会话。
          </div>
        </div>
      </div>

      <div class="panel preview-panel">
        <ArchivePreviewCard
          :report="store.state.selectedArchiveReport"
          :demo-videos="store.state.demoVideos"
        />
      </div>
    </section>
  </section>
</template>

<style scoped>
.records-page {
  display: grid;
  gap: 18px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card,
.panel {
  border-radius: 28px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(8, 17, 30, 0.76);
  backdrop-filter: blur(16px);
}

.summary-card {
  padding: 18px 20px;
}

.summary-card small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-card strong {
  display: block;
  margin-bottom: 6px;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.summary-card span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.summary-card.emphasis {
  background: linear-gradient(180deg, rgba(67, 215, 255, 0.1), rgba(8, 17, 30, 0.76));
}

.records-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(0, 1.1fr);
  gap: 18px;
}

.panel {
  padding: 22px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  letter-spacing: -0.03em;
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
  text-align: left;
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(255, 255, 255, 0.02);
  color: inherit;
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, background-color 180ms ease;
}

.archive-item::before {
  content: '';
  position: absolute;
  inset: 12px auto 12px 10px;
  width: 3px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.12);
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

.title-row {
  margin-bottom: 8px;
}

.title-row strong {
  font-size: 15px;
}

.title-row span,
.meta-row span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 180px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 1200px) {
  .records-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .summary-strip {
    grid-template-columns: 1fr;
  }

  .head {
    flex-direction: column;
  }
}
</style>
