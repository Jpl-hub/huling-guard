<script setup lang="ts">
import { computed } from 'vue'

import EventFeed from '../components/EventFeed.vue'
import MonitorStage from '../components/MonitorStage.vue'
import RiskTimelineChart from '../components/RiskTimelineChart.vue'
import SessionSummaryPanel from '../components/SessionSummaryPanel.vue'
import StateRibbon from '../components/StateRibbon.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatPercent, formatRisk, stateTone } from '../utils/presenters'

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
</script>

<template>
  <section class="live-page">
    <section class="answer-strip">
      <article
        v-for="answer in answerCards"
        :key="answer.label"
        class="answer-card"
        :data-tone="answer.tone"
      >
        <span>{{ answer.label }}</span>
        <strong>{{ answer.value }}</strong>
        <small>{{ answer.detail }}</small>
      </article>
    </section>

    <section class="workspace">
      <div class="stage-column">
        <MonitorStage
          :demo-videos="store.state.demoVideos"
          :selected-demo-filename="store.state.selectedDemoFilename"
          :live-source="store.state.liveSource"
          :live-frame-url="liveFrameUrl"
          :display-state="store.displayState.value"
          :report="store.displayReport.value"
          :source-detail="store.displaySource.value.detail"
          :view-mode="store.state.mode"
          @reload="store.refresh"
          @select-demo="store.selectDemo"
        />

        <section class="flow-panel">
          <header class="flow-head">
            <div>
              <span class="section-kicker">过程时间线</span>
              <h2>{{ store.state.mode === 'care' ? '状态变化' : '风险变化' }}</h2>
            </div>
            <span class="flow-chip">
              {{ store.displaySource.value.mode === 'demo' ? '模拟监看' : '实时接入' }}
            </span>
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
        <section
          class="command-deck"
          :data-tone="stateTone(store.displayState.value.predictedState, store.displayState.value.riskScore)"
        >
          <div class="command-head">
            <span class="command-badge">{{ store.verdict.value.badge }}</span>
            <span class="source-chip">{{ store.displaySource.value.detail }}</span>
          </div>

          <div class="command-copy">
            <small>{{ hasIncidents ? '请先确认画面并判断是否到场' : '当前系统判断' }}</small>
            <h2>{{ store.verdict.value.title }}</h2>
            <p>{{ store.verdict.value.detail }}</p>
          </div>

          <div class="command-metrics">
            <article>
              <span>建议动作</span>
              <strong>{{ store.verdict.value.action }}</strong>
            </article>
            <article>
              <span>当前风险</span>
              <strong>{{ formatRisk(store.displayState.value.riskScore) }}</strong>
            </article>
            <article>
              <span>最近事件</span>
              <strong>{{ store.displayIncidents.value.length ? `${store.displayIncidents.value.length} 条` : '无' }}</strong>
            </article>
          </div>

          <div class="command-steps">
            <span v-for="step in store.verdict.value.steps" :key="step">{{ step }}</span>
          </div>

          <div class="command-actions">
            <a-button type="primary" size="large" @click="store.archiveSession">归档当前会话</a-button>
            <a-button size="large" @click="store.resetRuntime">开始新会话</a-button>
          </div>
        </section>

        <section class="side-panel">
          <EventFeed :incidents="store.displayIncidents.value" :view-mode="store.state.mode" />
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
              <span class="section-kicker">算法透视</span>
              <h2>当前状态分布</h2>
            </div>
          </header>

          <div v-if="quality" class="quality-grid">
            <article class="quality-box">
              <span>骨架质量</span>
              <strong>{{ formatRisk(quality.pose_quality_score) }}</strong>
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
              <span>{{ state }}</span>
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
  gap: 20px;
}

.answer-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.answer-card,
.flow-panel,
.command-deck,
.side-panel {
  background: rgba(6, 14, 24, 0.74);
  backdrop-filter: blur(18px);
}

.answer-card {
  display: grid;
  gap: 8px;
  padding: 20px 0;
  border-top: 1px solid rgba(120, 146, 176, 0.16);
  border-bottom: 1px solid rgba(120, 146, 176, 0.16);
}

.answer-card span {
  color: rgba(199, 214, 231, 0.62);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.answer-card strong {
  font-size: clamp(24px, 3.2vw, 38px);
  line-height: 0.98;
  letter-spacing: -0.06em;
}

.answer-card small {
  color: rgba(199, 214, 231, 0.74);
  font-size: 13px;
}

.answer-card[data-tone='alert'] strong {
  color: #ffd6d2;
}

.answer-card[data-tone='watch'] strong {
  color: #ffe3b5;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(360px, 0.82fr);
  gap: 20px;
}

.stage-column,
.command-column {
  display: grid;
  gap: 20px;
}

.flow-panel,
.side-panel {
  border-radius: 28px;
  border: 1px solid rgba(120, 146, 176, 0.12);
  padding: 22px;
}

.flow-head,
.xray-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}

.section-kicker {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(143, 181, 221, 0.76);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.flow-head h2,
.xray-head h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.flow-chip,
.source-chip,
.command-badge {
  padding: 9px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.flow-chip,
.source-chip {
  background: rgba(255, 255, 255, 0.05);
  color: rgba(229, 237, 246, 0.8);
}

.command-deck {
  display: grid;
  gap: 18px;
  padding: 26px;
  border-radius: 30px;
  border: 1px solid rgba(120, 146, 176, 0.12);
}

.command-deck[data-tone='alert'] {
  background: linear-gradient(180deg, rgba(255, 94, 98, 0.16), rgba(6, 14, 24, 0.92));
}

.command-deck[data-tone='watch'] {
  background: linear-gradient(180deg, rgba(255, 179, 71, 0.16), rgba(6, 14, 24, 0.92));
}

.command-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.command-badge {
  width: fit-content;
  background: rgba(255, 255, 255, 0.08);
  color: #f4f8fb;
}

.command-copy small {
  display: block;
  margin-bottom: 10px;
  color: rgba(206, 220, 236, 0.62);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.command-copy h2 {
  margin: 0 0 8px;
  font-size: clamp(34px, 4vw, 50px);
  line-height: 0.98;
  letter-spacing: -0.06em;
}

.command-copy p {
  margin: 0;
  color: rgba(205, 219, 235, 0.76);
  line-height: 1.6;
}

.command-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.command-metrics article {
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.04);
}

.command-metrics span {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.62);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.command-metrics strong {
  font-size: 18px;
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.command-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.command-steps span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(224, 234, 244, 0.86);
  font-size: 13px;
}

.command-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.xray-panel {
  display: grid;
  gap: 14px;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.quality-box {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(120, 146, 176, 0.14);
}

.quality-box span {
  color: rgba(199, 214, 231, 0.68);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.quality-box strong {
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.probabilities {
  display: grid;
  gap: 12px;
}

.probability-row {
  display: grid;
  grid-template-columns: 88px 1fr 64px;
  gap: 12px;
  align-items: center;
}

.probability-row span,
.probability-row strong {
  font-size: 13px;
}

.track {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #43d7ff, #2f72ff);
}

.empty-inline {
  display: grid;
  place-items: center;
  min-height: 120px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
}

@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .answer-strip,
  .command-metrics,
  .quality-grid {
    grid-template-columns: 1fr;
  }
}
</style>
