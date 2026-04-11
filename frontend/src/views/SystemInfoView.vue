<script setup lang="ts">
import { computed } from 'vue'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk } from '../utils/presenters'

const store = useRuntimeStore()

const capabilityNotes: Record<string, string> = {
  normal: '持续确认当前是否安全，避免把日常活动都当成异常。',
  near_fall: '识别明显失衡趋势，用于提前提醒尽快查看。',
  fall: '检测到跌倒后直接进入高优先级风险处理。',
  recovery: '识别重新起身的过程，区分异常后恢复。',
  prolonged_lying: '对持续卧倒单独升级，避免漏掉长卧风险。',
}

const heroStats = computed(() => {
  const archiveTotal = store.state.archiveSummary?.archive_total ?? 0
  const incidentSessions = store.state.archiveSummary?.sessions_with_incidents ?? 0
  const detectableCount = store.state.systemProfile?.detectable_states?.length ?? 5

  return [
    {
      label: '输入入口',
      value: '实时接入 / 模拟监看 / 上传复核',
    },
    {
      label: '状态覆盖',
      value: `${detectableCount} 类连续状态`,
    },
    {
      label: '过程留档',
      value: archiveTotal > 0 ? `${archiveTotal} 段过程，${incidentSessions} 段含提醒` : '支持随时保存当前过程',
    },
  ]
})

const answerRows = computed(() => [
  {
    title: '当前是否安全',
    body: '持续判断当前状态和风险变化，避免把值守工作变成反复盯屏。',
  },
  {
    title: '是否需要马上过去',
    body: '把结论和建议动作分开给出，先帮助值守者做处理决定。',
  },
  {
    title: '最近到底发生了什么',
    body: '把连续视频变成可回看的过程记录，而不是零散截图。',
  },
])

const trustRows = computed(() => [
  {
    title: '按连续过程判断',
    body: '系统先建立连续时间窗，再输出状态和提醒，不按单帧乱判。',
  },
  {
    title: '低质量骨架保守处理',
    body: '关键点质量偏低时先降权，不把遮挡、低光和抖动直接抬成高风险。',
  },
  {
    title: '房间先验辅助',
    body: '结合房间语义先验区分床上躺卧与地面卧倒，减少正常躺卧误报。',
  },
  {
    title: '事件稳定化输出',
    body: '最终提醒经过 EventEngine 稳定，不把短时波动直接当成正式事件。',
  },
])

const boundaryColumns = computed(() => [
  {
    title: '适合的场景',
    items: [
      '单房间、固定机位、持续值守。',
      '关注老人是否安全、是否需要立即查看。',
      '需要过程留档和后续复核。',
    ],
  },
  {
    title: '当前可接入',
    items: [
      '本机摄像头或系统可见的视频设备。',
      'RTSP 视频流。',
      '本地视频文件。',
    ],
  },
  {
    title: '当前不主打',
    items: [
      '多路摄像头集中调度。',
      '频繁变焦、移动机位或大范围漫游。',
      '纯云端封闭、拿不到流地址的消费级摄像头。',
    ],
  },
])

const runtimeFacts = computed(() => {
  const meta = store.state.meta
  const profile = store.state.systemProfile?.runtime_profile
  const thresholds = store.state.systemProfile?.thresholds

  return [
    { label: '运行设备', value: meta?.device ?? profile?.device ?? '-' },
    { label: '时间窗', value: String(meta?.window_size ?? profile?.window_size ?? '-') },
    { label: '推理步长', value: String(meta?.inference_stride ?? profile?.inference_stride ?? '-') },
    { label: '特征集', value: meta?.kinematic_feature_set ?? profile?.kinematic_feature_set ?? '-' },
    { label: '跌倒阈值', value: formatRisk(thresholds?.fall) },
    { label: '长卧阈值', value: formatRisk(thresholds?.prolonged_lying) },
    { label: '场景先验', value: meta?.scene_prior_loaded || profile?.scene_prior_loaded ? '已加载' : '未加载' },
    { label: '历史归档', value: meta?.archive_enabled || profile?.archive_enabled ? '已开启' : '未开启' },
  ]
})

const targetUsers = computed(() => (store.state.systemProfile?.target_users ?? []).slice(0, 4))
const qualityControls = computed(() => (store.state.systemProfile?.quality_controls ?? []).slice(0, 4))
const moduleCards = computed(() => store.state.systemProfile?.system_modules ?? [])
const stateCards = computed(() => store.state.systemProfile?.detectable_states ?? [])
</script>

<template>
  <section class="system-page">
    <section class="hero panel">
      <div class="hero-copy">
        <small>{{ store.state.systemProfile?.product_name || '护龄智守' }}</small>
        <h2>把连续视频转成可处置的照护过程</h2>
        <p>
          持续给出当前状态、是否需要立即查看、最近发生的变化，并保留可复核的过程记录。
        </p>
        <div class="hero-users">
          <span v-for="user in targetUsers" :key="user">{{ user }}</span>
        </div>
      </div>

      <div class="hero-stats">
        <div v-for="item in heroStats" :key="item.label" class="hero-stat">
          <small>{{ item.label }}</small>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <section class="panel section">
      <header class="section-head">
        <h3>这套系统先回答三件事</h3>
        <p>先给结果，再给依据，不让用户自己在参数和图表里猜。</p>
      </header>

      <div class="answer-list">
        <article v-for="item in answerRows" :key="item.title" class="line-item">
          <strong>{{ item.title }}</strong>
          <p>{{ item.body }}</p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <header class="section-head">
        <h3>为何能信</h3>
        <p>先讲系统如何减少误报，再讲模型和参数。</p>
      </header>

      <div class="trust-list">
        <article v-for="item in trustRows" :key="item.title" class="line-item two-col">
          <strong>{{ item.title }}</strong>
          <p>{{ item.body }}</p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <header class="section-head">
        <h3>接入与边界</h3>
        <p>把适用范围写清楚，比含糊其辞更可靠。</p>
      </header>

      <div class="boundary-columns">
        <section v-for="group in boundaryColumns" :key="group.title" class="boundary-column">
          <h4>{{ group.title }}</h4>
          <ul>
            <li v-for="item in group.items" :key="item">{{ item }}</li>
          </ul>
        </section>
      </div>
    </section>

    <section class="panel section split-section">
      <div class="split-column">
        <header class="section-head compact-head">
          <h3>识别状态</h3>
          <p>不是只识别跌倒，而是识别完整动作过程。</p>
        </header>

        <div class="state-list">
          <article v-for="item in stateCards" :key="item.code" class="line-item two-col">
            <strong>{{ item.label }}</strong>
            <p>{{ capabilityNotes[item.code] || '系统会把这一类状态纳入连续判断。' }}</p>
          </article>
        </div>
      </div>

      <div class="split-column">
        <header class="section-head compact-head">
          <h3>运行链路</h3>
          <p>这里只保留真正影响结果的关键模块。</p>
        </header>

        <div class="module-list">
          <article v-for="module in moduleCards" :key="module.name" class="line-item two-col">
            <strong>{{ module.name }}</strong>
            <p>{{ module.summary }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="panel section">
      <details class="tech-drawer">
        <summary>
          <div>
            <strong>运行规格与版本口径</strong>
            <span>给技术评委和后续部署使用，不放进主操作界面。</span>
          </div>
        </summary>

        <div class="facts-grid">
          <article v-for="item in runtimeFacts" :key="item.label" class="fact-item">
            <small>{{ item.label }}</small>
            <strong>{{ item.value }}</strong>
          </article>
        </div>

        <div class="notes-grid">
          <section>
            <h4>质量控制</h4>
            <ul>
              <li v-for="item in qualityControls" :key="item">{{ item }}</li>
            </ul>
          </section>
          <section>
            <h4>当前版本态度</h4>
            <ul>
              <li>运行主干以稳定性优先，不因为单轮实验分数更高就直接替换。</li>
              <li>模型和系统同时看窗口级、样本级和应用级结果，避免只追单一指标。</li>
            </ul>
          </section>
        </div>
      </details>
    </section>
  </section>
</template>

<style scoped>
.system-page {
  display: grid;
  gap: 16px;
}

.panel {
  border-radius: 24px;
  background: rgba(8, 16, 28, 0.82);
  box-shadow: inset 0 0 0 1px rgba(126, 149, 178, 0.08);
}

.section {
  padding: 24px;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 24px;
  padding: 28px;
}

.hero-copy {
  display: grid;
  gap: 12px;
  align-content: start;
}

.hero-copy small,
.hero-stat small,
.fact-item small {
  color: rgba(193, 209, 226, 0.6);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.hero-copy h2 {
  margin: 0;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

.hero-copy p {
  margin: 0;
  max-width: 54ch;
  color: rgba(214, 226, 238, 0.78);
  font-size: 15px;
  line-height: 1.7;
}

.hero-users {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 4px;
}

.hero-users span {
  color: rgba(226, 236, 246, 0.88);
  font-size: 13px;
}

.hero-stats {
  display: grid;
  align-content: start;
  gap: 18px;
}

.hero-stat {
  display: grid;
  gap: 6px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(120, 146, 176, 0.12);
}

.hero-stat:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.hero-stat strong,
.fact-item strong {
  font-size: 18px;
  line-height: 1.45;
  letter-spacing: -0.03em;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h3,
.tech-drawer summary strong {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.04em;
}

.section-head p,
.tech-drawer summary span,
.line-item p,
.boundary-column li,
.notes-grid li {
  margin: 8px 0 0;
  color: rgba(206, 220, 235, 0.74);
  font-size: 14px;
  line-height: 1.7;
}

.answer-list,
.trust-list,
.state-list,
.module-list {
  display: grid;
}

.line-item {
  display: grid;
  gap: 8px;
  padding: 16px 0;
  border-top: 1px solid rgba(120, 146, 176, 0.1);
}

.line-item:first-child {
  padding-top: 0;
  border-top: none;
}

.line-item strong,
.boundary-column h4,
.notes-grid h4 {
  margin: 0;
  font-size: 17px;
  letter-spacing: -0.03em;
}

.two-col {
  grid-template-columns: minmax(160px, 220px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.two-col p {
  margin: 0;
}

.boundary-columns,
.notes-grid,
.facts-grid,
.split-section {
  display: grid;
  gap: 24px;
}

.boundary-columns {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.boundary-column {
  padding-left: 18px;
  border-left: 1px solid rgba(120, 146, 176, 0.12);
}

.boundary-column:first-child {
  padding-left: 0;
  border-left: none;
}

.boundary-column ul,
.notes-grid ul {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding-left: 18px;
}

.split-section {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.split-column + .split-column {
  padding-left: 24px;
  border-left: 1px solid rgba(120, 146, 176, 0.12);
}

.compact-head {
  margin-bottom: 10px;
}

.tech-drawer {
  display: grid;
  gap: 18px;
}

.tech-drawer summary {
  cursor: pointer;
  list-style: none;
}

.tech-drawer summary::-webkit-details-marker {
  display: none;
}

.tech-drawer summary div {
  display: grid;
  gap: 6px;
}

.facts-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.fact-item {
  display: grid;
  gap: 6px;
  padding: 14px 0;
  border-top: 1px solid rgba(120, 146, 176, 0.1);
}

.notes-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding-top: 6px;
}

@media (max-width: 1100px) {
  .hero,
  .split-section,
  .boundary-columns,
  .facts-grid,
  .notes-grid {
    grid-template-columns: 1fr;
  }

  .split-column + .split-column,
  .boundary-column {
    padding-left: 0;
    border-left: none;
  }
}

@media (max-width: 760px) {
  .two-col {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .hero,
  .section {
    padding: 16px;
  }

  .hero-copy h2 {
    font-size: 30px;
  }
}
</style>
