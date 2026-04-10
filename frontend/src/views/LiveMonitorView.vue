<script setup lang="ts">
import { computed } from 'vue'

import EventFeed from '../components/EventFeed.vue'
import MonitorStage from '../components/MonitorStage.vue'
import RiskTimelineChart from '../components/RiskTimelineChart.vue'
import SessionSummaryPanel from '../components/SessionSummaryPanel.vue'
import StateRibbon from '../components/StateRibbon.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk, stateTone } from '../utils/presenters'

const store = useRuntimeStore()

const answerCards = computed(() => store.quickAnswers.value)
const hasIncidents = computed(() => store.displayIncidents.value.length > 0)
const probabilityEntries = computed(() =>
  Object.entries(store.displayState.value.stateProbabilities)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 5),
)
</script>

<template>
  <section class="live-page">
    <section class="status-rail">
      <article
        v-for="answer in answerCards"
        :key="answer.label"
        class="status-item"
        :data-tone="answer.tone"
      >
        <span>{{ answer.label }}</span>
        <strong>{{ answer.value }}</strong>
        <small>{{ answer.detail }}</small>
      </article>
    </section>

    <section class="workspace">
      <div class="primary-column">
        <MonitorStage
          :demo-videos="store.state.demoVideos"
          :selected-demo-filename="store.state.selectedDemoFilename"
          :display-state="store.displayState.value"
          :report="store.displayReport.value"
          :source-detail="store.displaySource.value.detail"
          :view-mode="store.state.mode"
          @reload="store.refresh"
          @select-demo="store.selectDemo"
        />

        <div class="panel process-panel">
          <StateRibbon
            v-if="store.state.mode === 'care'"
            :report="store.displayReport.value"
            :incidents="store.displayIncidents.value"
          />
          <RiskTimelineChart v-else :items="store.displayTimeline.value?.items ?? []" />
        </div>
      </div>

      <div class="response-column">
        <section
          class="verdict-panel"
          :data-tone="stateTone(store.displayState.value.predictedState, store.displayState.value.riskScore)"
        >
          <div class="verdict-head">
            <span class="verdict-badge">{{ store.verdict.value.badge }}</span>
            <div class="verdict-state">
              <small>{{ hasIncidents ? '需要确认' : '当前判断' }}</small>
              <h2>{{ store.verdict.value.title }}</h2>
              <p>{{ store.verdict.value.detail }}</p>
            </div>
          </div>

          <div class="decision-line">
            <article class="decision-main">
              <span>下一步</span>
              <strong>{{ store.verdict.value.action }}</strong>
            </article>
            <article class="decision-side">
              <span>当前风险</span>
              <strong>{{ formatRisk(store.displayState.value.riskScore) }}</strong>
            </article>
            <article class="decision-side">
              <span>最近事件</span>
              <strong>{{ store.displayIncidents.value.length ? `${store.displayIncidents.value.length} 条` : '无' }}</strong>
            </article>
          </div>

          <div class="steps">
            <span v-for="step in store.verdict.value.steps" :key="step">{{ step }}</span>
          </div>

          <div class="actions">
            <a-button type="primary" size="large" @click="store.archiveSession">保存本段记录</a-button>
            <a-button size="large" @click="store.resetRuntime">开始新一段</a-button>
          </div>
        </section>

        <div class="panel">
          <EventFeed :incidents="store.displayIncidents.value" :view-mode="store.state.mode" />
        </div>

        <div class="panel">
          <SessionSummaryPanel
            :report="store.displayReport.value"
            :display-state="store.displayState.value"
            :runtime-chips="store.activeRuntimeChips.value"
            :view-mode="store.state.mode"
          />
        </div>

        <div v-if="store.state.mode === 'xray'" class="panel xray-panel">
          <header>
            <h2>引擎透视</h2>
            <p>这里展示状态分布和运行参数，默认值守视图不会显示这些工程细节。</p>
          </header>
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
          <div v-else class="empty-inline">当前还没有可展示的状态分布。</div>
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.live-page {
  display: grid;
  gap: 24px;
}

.status-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  padding: 8px 0 0;
  border-top: 1px solid rgba(120, 146, 176, 0.14);
  border-bottom: 1px solid rgba(120, 146, 176, 0.14);
}

.status-item,
.panel,
.verdict-panel {
  background: rgba(8, 17, 30, 0.76);
  backdrop-filter: blur(16px);
}

.status-item {
  display: grid;
  gap: 6px;
  padding: 18px 10px 18px 0;
}

.status-item + .status-item {
  padding-left: 18px;
  border-left: 1px solid rgba(120, 146, 176, 0.14);
}

.status-item span {
  color: rgba(199, 214, 231, 0.6);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.status-item strong {
  font-size: clamp(22px, 3vw, 34px);
  line-height: 1.04;
  letter-spacing: -0.05em;
}

.status-item small {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.4;
}

.status-item[data-tone='alert'] strong {
  color: #ffd3d0;
}

.status-item[data-tone='watch'] strong {
  color: #ffe3b5;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.78fr) minmax(360px, 0.82fr);
  gap: 20px;
}

.primary-column,
.response-column {
  display: grid;
  gap: 20px;
}

.panel {
  padding: 24px;
  border-radius: 30px;
  border: 1px solid rgba(120, 146, 176, 0.12);
}

.verdict-panel {
  display: grid;
  gap: 18px;
  padding: 28px;
  border-radius: 30px;
  border: 1px solid rgba(120, 146, 176, 0.12);
}

.verdict-panel[data-tone='alert'] {
  background: linear-gradient(180deg, rgba(255, 94, 98, 0.14), rgba(8, 17, 30, 0.88));
}

.verdict-panel[data-tone='watch'] {
  background: linear-gradient(180deg, rgba(255, 179, 71, 0.14), rgba(8, 17, 30, 0.88));
}

.verdict-head {
  display: grid;
  gap: 14px;
}

.verdict-badge {
  width: fit-content;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #dce8f5;
  font-size: 12px;
  font-weight: 700;
}

.verdict-state small {
  display: block;
  margin-bottom: 8px;
  color: rgba(206, 220, 236, 0.62);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.verdict-panel h2 {
  margin: 0 0 8px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.verdict-panel p {
  margin: 0;
  color: rgba(205, 219, 235, 0.76);
  line-height: 1.65;
}

.decision-line {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.decision-main,
.decision-side {
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.04);
}

.decision-main span,
.decision-side span {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.decision-main strong {
  font-size: 28px;
  line-height: 1.02;
  letter-spacing: -0.05em;
}

.decision-side strong {
  font-size: 18px;
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.steps {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.steps span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(224, 234, 244, 0.86);
  font-size: 13px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.process-panel {
  min-height: 250px;
}

.xray-panel header {
  margin-bottom: 16px;
}

.xray-panel h2 {
  margin: 0 0 6px;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.xray-panel p {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
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
  min-height: 140px;
  border-radius: 22px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  color: rgba(199, 214, 231, 0.62);
}

@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .status-rail,
  .decision-line {
    grid-template-columns: 1fr;
  }

  .status-item {
    padding-right: 0;
  }

  .status-item + .status-item {
    padding-left: 0;
    border-left: 0;
    border-top: 1px solid rgba(120, 146, 176, 0.14);
  }
}
</style>
