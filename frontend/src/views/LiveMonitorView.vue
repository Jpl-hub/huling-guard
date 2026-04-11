<script setup lang="ts">
import { computed } from 'vue'

import EventFeed from '../components/EventFeed.vue'
import MonitorStage from '../components/MonitorStage.vue'
import RiskTimelineChart from '../components/RiskTimelineChart.vue'
import SessionSummaryPanel from '../components/SessionSummaryPanel.vue'
import StateRibbon from '../components/StateRibbon.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import {
  formatPercent,
  formatRisk,
  formatSeconds,
  formatTimestamp,
  incidentLabel,
  stateLabel,
  stateTone,
} from '../utils/presenters'

const store = useRuntimeStore()

const answerCards = computed(() => store.quickAnswers.value)
const liveFrameUrl = computed(() => store.liveFrameUrl.value)
const probabilityEntries = computed(() =>
  Object.entries(store.displayState.value.stateProbabilities)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 5),
)
const quality = computed(() => store.currentDataQuality.value)
const pageTone = computed(() => stateTone(store.displayState.value.predictedState, store.displayState.value.riskScore))
const report = computed(() => store.displayReport.value)
const currentDurationText = computed(() =>
  report.value ? formatSeconds(report.value.duration_seconds) : '-',
)
const bannerFacts = computed(() => [
  {
    label: '是否安全',
    value: answerCards.value[0]?.value ?? '等待判断',
  },
  {
    label: '要不要去看',
    value: answerCards.value[1]?.value ?? store.verdict.value.action,
  },
  {
    label: '最近发生',
    value: answerCards.value[2]?.value ?? '暂无变化',
  },
])

const evidenceItems = computed(() => {
  const items: Array<{ label: string; value: string }> = []
  const latestIncident = store.displayIncidents.value[0]
  const longestSegment = report.value?.longest_segments?.[0]

  if (latestIncident) {
    items.push({
      label: '最近变化',
      value: `${incidentLabel(latestIncident.kind)} · ${formatTimestamp(latestIncident.timestamp)}`,
    })
  } else if ((report.value?.total_frames ?? 0) > 0 && !store.displayState.value.ready) {
    items.push({
      label: '最近变化',
      value: report.value?.ready_frames
        ? `系统正在就绪 · ${report.value.ready_frames} 帧`
        : '系统正在就绪。',
    })
  } else {
    items.push({
      label: '最近变化',
      value: '暂无正式提醒。',
    })
  }

  if (report.value?.peak_risk) {
    items.push({
      label: '风险高点',
      value: `${formatTimestamp(report.value.peak_risk.timestamp)} 达到 ${formatRisk(report.value.peak_risk.risk_score)}`,
    })
  }

  if (longestSegment) {
    items.push({
      label: '持续最久的状态',
      value: `${stateLabel(longestSegment.state)} · ${formatSeconds(longestSegment.duration_seconds)}`,
    })
  }

  if (quality.value) {
    items.push({
      label: '骨架质量',
      value:
        quality.value.pose_quality_score < 0.45
          ? `偏低 · ${formatPercent(quality.value.pose_quality_score)}`
          : `稳定 · ${formatPercent(quality.value.pose_quality_score)}`,
    })
  }

  return items.slice(0, 3)
})

const nextSteps = computed(() => store.verdict.value.steps.slice(0, 2))
const flowTitle = computed(() => (store.state.mode === 'care' ? '最近 10 秒过程' : '算法透视'))
const flowDescription = computed(() =>
  store.state.mode === 'care'
    ? '按时间顺序查看状态变化。'
    : '查看状态分布、骨架质量和运行参数。',
)
</script>

<template>
  <section class="live-page">
    <section class="status-banner" :data-tone="pageTone">
      <div class="banner-main">
        <div class="banner-meta">
          <span class="banner-mode">{{ store.displaySource.value.detail }}</span>
          <span class="banner-source">{{ store.displaySource.value.label }}</span>
        </div>
        <h1>{{ answerCards[0]?.value ?? store.verdict.value.title }}</h1>
        <p>{{ store.verdict.value.detail }}</p>
      </div>

      <dl class="banner-strip">
        <div v-for="fact in bannerFacts" :key="fact.label" class="banner-stat">
          <dt>{{ fact.label }}</dt>
          <dd>{{ fact.value }}</dd>
        </div>
      </dl>
    </section>

    <section class="workspace">
      <div class="stage-column">
        <MonitorStage
          :demo-videos="store.state.demoVideos"
          :selected-demo-filename="store.state.selectedDemoFilename"
          :live-source="store.state.liveSource"
          :live-ingest="store.state.liveIngest"
          :live-frame-url="liveFrameUrl"
          :display-state="store.displayState.value"
          :report="store.displayReport.value"
          :source-detail="store.displaySource.value.detail"
          :uploading="store.state.uploadingVideo"
          :view-mode="store.state.mode"
          @reload="store.refresh"
          @select-demo="store.selectDemo"
          @upload-video="store.uploadVideo"
          @start-live-ingest="store.startLiveIngest"
          @stop-live-ingest="store.stopLiveIngest"
          @playback-update="store.updateDemoPlayback"
        />

        <section class="flow-panel">
          <header class="flow-head">
            <div>
              <h2>{{ flowTitle }}</h2>
              <p>{{ flowDescription }}</p>
            </div>
            <span class="flow-chip">{{ store.state.mode === 'care' ? '过程视图' : '引擎透视' }}</span>
          </header>

          <StateRibbon
            v-if="store.state.mode === 'care'"
            :report="store.displayReport.value"
            :incidents="store.displayIncidents.value"
          />
          <RiskTimelineChart v-else :items="store.displayTimeline.value?.items ?? []" />
        </section>
      </div>

      <aside class="command-column">
        <section class="decision-panel" :data-tone="pageTone">
          <div class="decision-head">
            <span class="decision-badge">{{ store.verdict.value.badge }}</span>
            <span class="source-chip">{{ store.displaySource.value.detail }}</span>
          </div>

          <div class="decision-copy">
            <small>核心判定</small>
            <h2>{{ store.verdict.value.action }}</h2>
            <p>这段画面已连续判断 {{ currentDurationText }}。</p>
          </div>

          <div class="decision-inline">
            <article>
              <span>当前风险</span>
              <strong>{{ formatRisk(store.displayState.value.riskScore) }}</strong>
            </article>
            <article>
              <span>最近提醒</span>
              <strong>{{ store.displayIncidents.value.length ? `${store.displayIncidents.value.length} 条` : '无' }}</strong>
            </article>
            <article>
              <span>本段时长</span>
              <strong>{{ currentDurationText }}</strong>
            </article>
          </div>

          <div class="evidence-block">
            <header>
              <h3>核心判定</h3>
            </header>
            <ul>
              <li v-for="item in evidenceItems" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </li>
            </ul>
          </div>

          <div class="action-block">
            <header>
              <h3>处置建议</h3>
            </header>
            <ol>
              <li v-for="step in nextSteps" :key="step">{{ step }}</li>
            </ol>
          </div>

          <div class="command-actions">
            <a-button type="primary" size="large" @click="store.archiveSession">保存到历史回看</a-button>
            <a-button size="large" @click="store.resetRuntime">重新开始判断</a-button>
          </div>
        </section>

        <section class="side-panel">
          <EventFeed
            :incidents="store.displayIncidents.value"
            :display-state="store.displayState.value"
            :report="store.displayReport.value"
            :view-mode="store.state.mode"
          />
        </section>

        <section class="side-panel">
          <SessionSummaryPanel
            :report="store.displayReport.value"
            :display-state="store.displayState.value"
            :runtime-chips="store.activeRuntimeChips.value"
            :view-mode="store.state.mode"
          />
        </section>

        <section v-if="store.state.mode === 'xray'" class="side-panel xray-panel">
          <header class="xray-head">
            <div>
              <h2>算法透视</h2>
              <p>状态分布、骨架质量与运行参数。</p>
            </div>
          </header>

          <div v-if="quality" class="quality-grid">
            <article class="quality-box">
              <span>骨架质量</span>
              <strong>{{ formatPercent(quality.pose_quality_score) }}</strong>
            </article>
            <article class="quality-box">
              <span>关键点均值</span>
              <strong>{{ formatPercent(quality.mean_keypoint_confidence) }}</strong>
            </article>
            <article class="quality-box">
              <span>可见关节</span>
              <strong>{{ formatPercent(quality.visible_joint_ratio) }}</strong>
            </article>
          </div>

          <div v-if="probabilityEntries.length" class="probabilities">
            <article
              v-for="[state, probability] in probabilityEntries"
              :key="state"
              class="probability-row"
            >
              <span>{{ stateLabel(state as any) }}</span>
              <div class="track">
                <div class="fill" :style="{ width: `${Math.max(4, Number(probability) * 100)}%` }" />
              </div>
              <strong>{{ formatRisk(Number(probability)) }}</strong>
            </article>
          </div>
          <div v-else class="empty-inline">当前没有可展示的状态分布。</div>
        </section>
      </aside>
    </section>
  </section>
</template>

<style scoped>
.live-page {
  display: grid;
  gap: var(--space-6);
}

.status-banner {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(0, 1fr);
  gap: var(--space-6);
  align-items: end;
  padding: 0 0 var(--space-5);
  border-bottom: 1px solid var(--color-line-soft);
}

.status-banner[data-tone='alert'] {
  border-bottom-color: rgba(255, 140, 144, 0.3);
}

.status-banner[data-tone='watch'] {
  border-bottom-color: rgba(242, 202, 123, 0.3);
}

.banner-main {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.banner-meta {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  align-items: center;
}

.banner-mode,
.banner-source,
.flow-chip,
.decision-badge,
.source-chip {
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.banner-main h1 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: clamp(28px, 3.4vw, 44px);
  line-height: 0.96;
  letter-spacing: -0.06em;
}

.banner-main p {
  margin: 0;
  max-width: 58ch;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.banner-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  margin: 0;
}

.banner-stat {
  padding-left: var(--space-4);
  border-left: 1px solid var(--color-line-soft);
}

.banner-stat dt {
  margin-bottom: var(--space-2);
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.banner-stat dd {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 18px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.72fr) minmax(320px, 0.68fr);
  gap: var(--space-7);
}

.stage-column,
.command-column {
  display: grid;
  gap: var(--space-6);
}

.command-column {
  align-content: start;
  padding-left: var(--space-7);
  border-left: 1px solid var(--color-line-soft);
}

.flow-panel,
.side-panel,
.decision-panel {
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
}

.flow-panel,
.side-panel {
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-line-soft);
}

.flow-head,
.xray-head,
.evidence-block header,
.action-block header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
}

.flow-head h2,
.xray-head h2,
.evidence-block h3,
.action-block h3 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.03em;
}

.flow-head p,
.xray-head p,
.evidence-block p,
.action-block p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.decision-panel {
  display: grid;
  gap: var(--space-5);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-line-soft);
}

.decision-panel[data-tone='alert'] {
  border-bottom-color: rgba(255, 140, 144, 0.3);
}

.decision-panel[data-tone='watch'] {
  border-bottom-color: rgba(242, 202, 123, 0.3);
}

.decision-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
}

.decision-copy small {
  display: inline-block;
  margin-bottom: var(--space-3);
  color: var(--color-text-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.decision-copy h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: clamp(30px, 3.2vw, 42px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.decision-copy p {
  margin: 10px 0 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.decision-inline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.decision-inline article {
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line-soft);
}

.decision-inline span {
  display: block;
  margin-bottom: var(--space-2);
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.decision-inline strong {
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.evidence-block,
.action-block {
  display: grid;
  gap: var(--space-3);
}

.evidence-block ul,
.action-block ol {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.evidence-block li,
.action-block li {
  display: grid;
  gap: 6px;
  padding: 14px 0;
  border-top: 1px solid var(--color-line-soft);
}

.evidence-block li span,
.action-block li::marker {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.evidence-block li strong,
.action-block li {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-primary);
}

.action-block ol {
  list-style: decimal;
  padding-left: 18px;
}

.command-actions {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.quality-box {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-line-soft);
}

.quality-box span {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.quality-box strong {
  color: var(--color-text-primary);
  font-size: 24px;
  letter-spacing: -0.04em;
}

.probabilities {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.probability-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 56px;
  gap: var(--space-3);
  align-items: center;
}

.probability-row span {
  color: var(--color-text-primary);
  font-size: 13px;
}

.track {
  position: relative;
  height: 8px;
  border-radius: 999px;
  background: var(--color-surface-soft);
  overflow: hidden;
}

.fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: var(--color-accent);
}

.probability-row strong {
  font-size: 13px;
  text-align: right;
  color: var(--color-text-primary);
}

.empty-inline {
  display: grid;
  place-items: center;
  min-height: 120px;
  color: var(--color-text-tertiary);
  text-align: center;
}

@media (max-width: 1200px) {
  .status-banner {
    grid-template-columns: 1fr;
  }

  .banner-strip {
    width: 100%;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .command-column {
    padding-left: 0;
    border-left: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .decision-panel,
  .xray-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .banner-strip,
  .decision-inline,
  .quality-grid,
  .command-column,
  .probability-row {
    grid-template-columns: 1fr;
  }

  .command-column {
    gap: var(--space-5);
  }

  .banner-stat {
    padding-top: var(--space-3);
    padding-left: 0;
    border-top: 1px solid var(--color-line-soft);
    border-left: 0;
  }
}

@media (max-width: 640px) {
  .status-banner {
    padding-bottom: var(--space-4);
  }

  .banner-main h1,
  .decision-copy h2 {
    font-size: 24px;
  }
}
</style>
