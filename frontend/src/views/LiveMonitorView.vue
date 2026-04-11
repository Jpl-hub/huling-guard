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
const hasIncidents = computed(() => store.displayIncidents.value.length > 0)
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
        ? `已形成 ${report.value.ready_frames} 帧连续判断，等待正式提醒。`
        : '系统已进入分析，正在建立时序窗口。',
    })
  } else {
    items.push({
      label: '最近变化',
      value: '这段画面还没有形成正式提醒。',
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
          ? `当前偏低（${formatPercent(quality.value.pose_quality_score)}），系统会更保守。`
          : `当前稳定（${formatPercent(quality.value.pose_quality_score)}），可以形成连续判断。`,
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
const actionHint = computed(() =>
  store.state.meta?.archive_enabled
    ? '保存到历史回看：把当前这段放进历史回看。开始新一段：清空当前这段，重新累计。'
    : '当前环境还没有开启历史回看。',
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
            <small>{{ hasIncidents ? '先判断要不要马上过去' : '当前以继续值守为主' }}</small>
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
              <h3>判断依据</h3>
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
              <h3>接下来怎么做</h3>
            </header>
            <ol>
              <li v-for="step in nextSteps" :key="step">{{ step }}</li>
            </ol>
          </div>

          <div class="command-actions">
            <a-button type="primary" size="large" @click="store.archiveSession">保存到历史回看</a-button>
            <a-button size="large" @click="store.resetRuntime">开始新一段</a-button>
          </div>

          <p class="action-hint">{{ actionHint }}</p>
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
  gap: 18px;
}

.status-banner {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  padding: 16px 18px;
  border-radius: 24px;
  background: rgba(6, 14, 24, 0.68);
  backdrop-filter: blur(16px);
}

.status-banner[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px rgba(255, 90, 94, 0.24), 0 18px 46px rgba(255, 90, 94, 0.12);
}

.status-banner[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px rgba(255, 192, 90, 0.2), 0 18px 46px rgba(255, 192, 90, 0.08);
}

.banner-main {
  display: grid;
  gap: 8px;
  min-width: 320px;
}

.banner-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.banner-mode,
.banner-source,
.flow-chip,
.decision-badge,
.source-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(226, 236, 246, 0.86);
  font-size: 12px;
  font-weight: 700;
}

.banner-main h1 {
  margin: 0;
  font-size: clamp(28px, 3.4vw, 44px);
  line-height: 0.96;
  letter-spacing: -0.06em;
}

.banner-main p {
  margin: 0;
  max-width: 58ch;
  color: rgba(213, 224, 237, 0.74);
  font-size: 13px;
}

.banner-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
  width: min(760px, 100%);
}

.banner-stat {
  padding-left: 16px;
  border-left: 1px solid rgba(110, 141, 176, 0.16);
}

.banner-stat dt {
  margin-bottom: 8px;
  color: rgba(190, 207, 226, 0.62);
  font-size: 12px;
}

.banner-stat dd {
  margin: 0;
  font-size: 18px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(340px, 0.62fr);
  gap: 18px;
}

.stage-column,
.command-column {
  display: grid;
  gap: 18px;
}

.command-column {
  align-content: start;
  padding: 22px;
  border-radius: 30px;
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.flow-panel,
.side-panel,
.decision-panel {
  border-radius: 30px;
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.flow-panel {
  padding: 22px;
}

.side-panel {
  padding: 18px 0 0;
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
  border-top: 1px solid rgba(110, 141, 176, 0.12);
}

.flow-head,
.xray-head,
.evidence-block header,
.action-block header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
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
  margin: 8px 0 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 13px;
}

.decision-panel {
  display: grid;
  gap: 22px;
  padding: 0 0 18px;
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
  border-bottom: 1px solid rgba(110, 141, 176, 0.12);
}

.decision-panel[data-tone='alert'] {
  border-bottom-color: rgba(255, 90, 94, 0.32);
}

.decision-panel[data-tone='watch'] {
  border-bottom-color: rgba(255, 192, 90, 0.28);
}

.decision-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.decision-copy small {
  display: inline-block;
  margin-bottom: 12px;
  color: rgba(199, 214, 231, 0.58);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.decision-copy h2 {
  margin: 0;
  font-size: clamp(28px, 3.2vw, 40px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.decision-copy p {
  margin: 10px 0 0;
  color: rgba(214, 225, 237, 0.74);
  font-size: 14px;
}

.decision-inline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.decision-inline article {
  padding-top: 14px;
  border-top: 1px solid rgba(110, 141, 176, 0.14);
}

.decision-inline span {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.62);
  font-size: 12px;
}

.decision-inline strong {
  font-size: 22px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.evidence-block,
.action-block {
  display: grid;
  gap: 14px;
}

.evidence-block ul,
.action-block ol {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.evidence-block li,
.action-block li {
  display: grid;
  gap: 6px;
  padding: 14px 0;
  border-top: 1px solid rgba(110, 141, 176, 0.12);
}

.evidence-block li span,
.action-block li::marker {
  color: rgba(199, 214, 231, 0.58);
  font-size: 12px;
}

.evidence-block li strong,
.action-block li {
  font-size: 14px;
  line-height: 1.6;
  color: rgba(236, 243, 250, 0.94);
}

.action-block ol {
  list-style: decimal;
  padding-left: 18px;
}

.command-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-hint {
  margin: 10px 0 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 12px;
  line-height: 1.6;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.quality-box {
  display: grid;
  gap: 8px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.03);
}

.quality-box span {
  color: rgba(199, 214, 231, 0.62);
  font-size: 12px;
}

.quality-box strong {
  font-size: 24px;
  letter-spacing: -0.04em;
}

.probabilities {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.probability-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 56px;
  gap: 12px;
  align-items: center;
}

.probability-row span {
  color: rgba(230, 238, 247, 0.86);
  font-size: 13px;
}

.track {
  position: relative;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: rgba(67, 215, 255, 0.84);
}

.probability-row strong {
  font-size: 13px;
  text-align: right;
  color: rgba(232, 240, 249, 0.88);
}

.empty-inline {
  display: grid;
  place-items: center;
  min-height: 120px;
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}

@media (max-width: 1200px) {
  .status-banner {
    flex-direction: column;
    align-items: stretch;
  }

  .banner-main {
    min-width: 0;
  }

  .banner-strip {
    width: 100%;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .command-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .decision-panel {
    grid-column: 1 / -1;
  }

  .xray-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .banner-strip,
  .decision-inline,
  .quality-grid {
    grid-template-columns: 1fr;
  }

  .status-banner,
  .flow-panel,
  .command-column {
    padding: 18px;
  }

  .banner-stat {
    padding-top: 12px;
    padding-left: 0;
    border-top: 1px solid rgba(110, 141, 176, 0.16);
    border-left: 0;
  }

  .decision-panel {
    padding: 0 0 18px;
  }

  .command-column {
    grid-template-columns: 1fr;
  }

  .probability-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .status-banner,
  .flow-panel,
  .command-column {
    padding: 14px;
    border-radius: 22px;
  }

  .banner-main h1 {
    font-size: 24px;
  }

  .decision-copy h2 {
    font-size: 24px;
  }
}
</style>
