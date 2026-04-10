<script setup lang="ts">
import { computed } from 'vue'

import EventFeed from '../components/EventFeed.vue'
import MonitorStage from '../components/MonitorStage.vue'
import RiskTimelineChart from '../components/RiskTimelineChart.vue'
import SessionSummaryPanel from '../components/SessionSummaryPanel.vue'
import StateRibbon from '../components/StateRibbon.vue'
import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk, stateLabel, stateTone } from '../utils/presenters'

const store = useRuntimeStore()

const answerCards = computed(() => store.quickAnswers.value)
const probabilityEntries = computed(() =>
  Object.entries(store.displayState.value.stateProbabilities)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 5),
)
</script>

<template>
  <section class="live-page">
    <div class="answer-strip">
      <article
        v-for="answer in answerCards"
        :key="answer.label"
        class="answer-card"
        :data-tone="answer.tone"
      >
        <small>{{ answer.label }}</small>
        <strong>{{ answer.value }}</strong>
        <span>{{ answer.detail }}</span>
      </article>
    </div>

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
          <span class="verdict-badge">{{ store.verdict.value.badge }}</span>
          <h2>{{ store.verdict.value.title }}</h2>
          <p>{{ store.verdict.value.detail }}</p>

          <div class="verdict-kpis">
            <article>
              <small>建议动作</small>
              <strong>{{ store.verdict.value.action }}</strong>
            </article>
            <article>
              <small>当前状态</small>
              <strong>{{ stateLabel(store.displayState.value.predictedState ?? null) }}</strong>
            </article>
            <article v-if="store.state.mode === 'xray'">
              <small>当前风险</small>
              <strong>{{ formatRisk(store.displayState.value.riskScore) }}</strong>
            </article>
            <article v-else>
              <small>最近事件</small>
              <strong>{{ store.displayIncidents.value.length ? `${store.displayIncidents.value.length} 条` : '当前无事件' }}</strong>
            </article>
          </div>

          <ul class="steps">
            <li v-for="step in store.verdict.value.steps" :key="step">{{ step }}</li>
          </ul>

          <div class="actions">
            <a-button type="primary" size="large" @click="store.archiveSession">归档本次会话</a-button>
            <a-button size="large" @click="store.resetRuntime">重置当前会话</a-button>
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
  gap: 20px;
}

.answer-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.answer-card,
.panel,
.verdict-panel {
  border-radius: 30px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(8, 17, 30, 0.76);
  backdrop-filter: blur(16px);
}

.answer-card {
  padding: 20px 22px;
}

.answer-card small {
  display: block;
  margin-bottom: 10px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.answer-card strong {
  display: block;
  margin-bottom: 6px;
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.answer-card span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.5;
}

.answer-card[data-tone='alert'] {
  background: linear-gradient(180deg, rgba(255, 94, 98, 0.12), rgba(8, 17, 30, 0.8));
}

.answer-card[data-tone='watch'] {
  background: linear-gradient(180deg, rgba(255, 179, 71, 0.12), rgba(8, 17, 30, 0.8));
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(360px, 0.86fr);
  gap: 20px;
}

.primary-column,
.response-column {
  display: grid;
  gap: 20px;
}

.panel {
  padding: 24px;
}

.verdict-panel {
  display: grid;
  gap: 18px;
  padding: 26px;
}

.verdict-panel[data-tone='alert'] {
  background: linear-gradient(180deg, rgba(255, 94, 98, 0.14), rgba(8, 17, 30, 0.88));
}

.verdict-panel[data-tone='watch'] {
  background: linear-gradient(180deg, rgba(255, 179, 71, 0.14), rgba(8, 17, 30, 0.88));
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

.verdict-panel h2 {
  margin: 0;
  font-size: clamp(30px, 4vw, 46px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.verdict-panel p {
  margin: 0;
  color: rgba(205, 219, 235, 0.76);
  line-height: 1.65;
}

.verdict-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.verdict-kpis article {
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.04);
}

.verdict-kpis small {
  display: block;
  margin-bottom: 8px;
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.verdict-kpis strong {
  font-size: 18px;
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.steps {
  display: grid;
  gap: 10px;
  padding-left: 18px;
  margin: 0;
  color: rgba(224, 234, 244, 0.86);
  line-height: 1.65;
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
  .answer-strip,
  .verdict-kpis {
    grid-template-columns: 1fr;
  }
}
</style>
