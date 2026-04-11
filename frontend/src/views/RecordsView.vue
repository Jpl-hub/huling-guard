<script setup lang="ts">
import { computed } from 'vue'

import ArchivePreviewCard from '../components/ArchivePreviewCard.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { matchDemoVideo } from '../utils/media'
import { archiveDisplayName, formatArchiveTime, formatRisk, formatSeconds, stateLabel } from '../utils/presenters'

const store = useRuntimeStore()

const overviewCards = computed(() => [
  {
    label: '已归档过程',
    value: String(store.state.archiveSummary?.archive_total ?? 0),
    detail: '所有已保存的过程都会在这里回看。',
  },
  {
    label: '需要优先复核',
    value: String(store.state.archiveSummary?.sessions_with_incidents ?? 0),
    detail: '先看出现提醒的过程，再回看正常过程做对照。',
  },
  {
    label: '最近一条结论',
    value: stateLabel(store.state.archiveSummary?.latest_archive?.dominant_state ?? null),
    detail: formatArchiveTime(store.state.archiveSummary?.latest_archive?.archived_at ?? null),
  },
])

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
</script>

<template>
  <section class="records-page">
    <section class="overview-band">
      <div class="overview-copy">
        <h2>历史回看</h2>
        <p>把已经发生过的一整段过程拉出来复查，先看是否真的需要干预，再看系统是不是判断准确。</p>
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
            <h2>选择一段过程</h2>
            <p>点击左侧记录，右侧会展开完整过程、关键时刻和回放入口。</p>
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
              <a-option value="near_fall">失衡风险</a-option>
              <a-option value="fall">跌倒</a-option>
              <a-option value="recovery">恢复起身</a-option>
              <a-option value="prolonged_lying">长卧风险</a-option>
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
            v-for="entry in archiveEntries"
            :key="entry.item.session_id"
            type="button"
            class="archive-item"
            :class="{ active: entry.item.session_id === store.state.selectedArchiveId }"
            @click="store.loadArchive(entry.item.session_id)"
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
                  <span class="state-pill">{{ stateLabel(entry.item.dominant_state) }}</span>
                </div>
                <div class="meta-row">
                  <span>时长 {{ formatSeconds(entry.item.duration_seconds) }}</span>
                  <span>{{ entry.item.incident_total > 0 ? `提醒 ${entry.item.incident_total} 次` : '没有正式提醒' }}</span>
                  <span>峰值 {{ formatRisk(entry.item.peak_risk_score) }}</span>
                </div>
              </div>
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
  gap: 18px;
}

.overview-band {
  display: grid;
  gap: 18px;
  padding: 24px 26px;
  border-radius: 30px;
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.overview-copy {
  display: grid;
  gap: 10px;
}

.overview-copy h2 {
  margin: 0;
  font-size: 34px;
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.overview-copy p {
  margin: 0;
  max-width: 72ch;
  color: rgba(199, 214, 231, 0.74);
  font-size: 14px;
  line-height: 1.6;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.overview-item,
.records-list,
.preview-panel {
  border-radius: 30px;
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.overview-item {
  padding: 18px 20px;
}

.overview-item small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.58);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.overview-item strong {
  display: block;
  margin-bottom: 6px;
  font-size: 28px;
  letter-spacing: -0.05em;
}

.overview-item span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
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
  align-items: flex-start;
  margin-bottom: 18px;
}

.records-head h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.records-head p {
  margin: 8px 0 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 13px;
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
  gap: 10px;
  text-align: left;
  padding: 18px 18px 18px 22px;
  border-radius: 24px;
  border: 0;
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
  transition: transform 180ms ease, background-color 180ms ease, box-shadow 180ms ease;
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
  background: rgba(67, 215, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(67, 215, 255, 0.22);
}

.archive-item.active::before {
  background: #43d7ff;
}

.archive-row {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
}

.archive-thumb {
  overflow: hidden;
  border-radius: 18px;
  background: #07111d;
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
  gap: 12px;
}

.title-row,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.title-row strong {
  display: block;
  margin-bottom: 6px;
  font-size: 16px;
}

.title-row p {
  margin: 0;
  color: rgba(199, 214, 231, 0.62);
  font-size: 12px;
}

.state-pill {
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.14);
  color: #d9f7ff;
  font-size: 12px;
  font-weight: 700;
}

.meta-row span {
  color: rgba(199, 214, 231, 0.74);
  font-size: 12px;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 200px;
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 1200px) {
  .records-layout,
  .overview-stats {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .overview-band,
  .records-list,
  .preview-panel {
    padding: 16px;
    border-radius: 22px;
  }

  .records-head {
    flex-direction: column;
  }

  .archive-row {
    grid-template-columns: 1fr;
  }
}
</style>
