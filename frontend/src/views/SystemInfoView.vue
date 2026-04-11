<script setup lang="ts">
import { computed } from 'vue'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk } from '../utils/presenters'

const store = useRuntimeStore()

const capabilityNotes: Record<string, string> = {
  normal: '持续确认当前是否安全，避免把日常活动都当成异常。',
  near_fall: '捕捉明显失衡趋势，用于提前提醒尽快查看。',
  fall: '检测到跌倒后直接进入高优先级风险处理。',
  recovery: '识别已经重新起身的过程，区分异常后恢复。',
  prolonged_lying: '对持续卧倒单独升级，避免漏掉长卧风险。',
}

const heroStats = computed(() => {
  const detectableCount = store.state.systemProfile?.detectable_states?.length ?? 5
  const archiveTotal = store.state.archiveSummary?.archive_total ?? 0
  const incidentSessions = store.state.archiveSummary?.sessions_with_incidents ?? 0

  return [
    {
      label: '输入入口',
      value: '3 种',
      detail: '实时接入、模拟监看、上传复核',
    },
    {
      label: '连续状态',
      value: `${detectableCount} 类`,
      detail: '不是只看跌倒，而是识别完整过程。',
    },
    {
      label: '过程留档',
      value: archiveTotal > 0 ? `${archiveTotal} 段` : '随时可留档',
      detail: incidentSessions > 0 ? `其中 ${incidentSessions} 段含提醒记录。` : '用于回看、复核和后续优化。',
    },
  ]
})

const storyCards = computed(() => [
  {
    title: '当前是否安全',
    body: '持续判断当前状态和风险变化，不把值守工作变成反复盯屏。',
  },
  {
    title: '是否需要马上过去',
    body: '把提醒和建议动作分开给出，先帮助值守者做出处理决定。',
  },
  {
    title: '最近到底发生了什么',
    body: '把连续视频转成可回放的过程记录，而不是零散截图。',
  },
])

const trustCards = computed(() => [
  {
    title: '连续过程判断',
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
    body: '最终提醒经过 EventEngine 稳定，不把短时波动直接当成事件。',
  },
])

const boundaryGroups = computed(() => [
  {
    title: '适合的场景',
    items: [
      '单房间、固定机位、持续值守。',
      '关注老人是否安全、是否需要立即查看。',
      '需要过程留档和后续复核，而不是只看单帧结果。',
    ],
  },
  {
    title: '当前可接入',
    items: [
      '本机摄像头或系统可见的视频设备。',
      'RTSP 视频流。',
      '本地视频文件，用于上传复核和模拟监看。',
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
    {
      label: '场景先验',
      value: meta?.scene_prior_loaded || profile?.scene_prior_loaded ? '已加载' : '未加载',
    },
    {
      label: '历史归档',
      value: meta?.archive_enabled || profile?.archive_enabled ? '已开启' : '未开启',
    },
  ]
})

const moduleCards = computed(() => store.state.systemProfile?.system_modules ?? [])
const stateCards = computed(() => store.state.systemProfile?.detectable_states ?? [])
const targetUsers = computed(() => (store.state.systemProfile?.target_users ?? []).slice(0, 4))
const qualityControls = computed(() => (store.state.systemProfile?.quality_controls ?? []).slice(0, 4))
</script>

<template>
  <section class="system-page">
    <section class="hero panel">
      <div class="hero-copy">
        <small>{{ store.state.systemProfile?.product_name || '护龄智守' }}</small>
        <h2>把连续视频转成可处置的照护过程</h2>
        <p>
          不是只看有没有倒地，而是持续判断当前状态、风险变化、是否需要立即查看，并保留可复核的过程记录。
        </p>
      </div>

      <dl class="hero-stats">
        <div v-for="item in heroStats" :key="item.label" class="stat-card">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
          <span>{{ item.detail }}</span>
        </div>
      </dl>
    </section>

    <section class="panel section intro-section">
      <header class="section-head">
        <div>
          <h3>系统先回答三件事</h3>
          <p>页面先给结果，再给依据，不让用户在参数和图表里自己猜。</p>
        </div>
      </header>

      <div class="story-grid">
        <article v-for="item in storyCards" :key="item.title" class="story-card">
          <strong>{{ item.title }}</strong>
          <p>{{ item.body }}</p>
        </article>
      </div>
    </section>

    <section class="system-layout">
      <article class="panel section">
        <header class="section-head">
          <div>
            <h3>适用对象</h3>
            <p>这套系统优先服务固定房间照护和值守场景。</p>
          </div>
        </header>
        <ul class="bullet-list">
          <li v-for="user in targetUsers" :key="user">{{ user }}</li>
        </ul>
      </article>

      <article class="panel section">
        <header class="section-head">
          <div>
            <h3>为什么可信</h3>
            <p>先讲系统如何减少误报，再讲底层模型和参数。</p>
          </div>
        </header>
        <div class="trust-grid">
          <article v-for="item in trustCards" :key="item.title" class="soft-card trust-card">
            <strong>{{ item.title }}</strong>
            <p>{{ item.body }}</p>
          </article>
        </div>
      </article>

      <article class="panel section full-span">
        <header class="section-head">
          <div>
            <h3>适用边界</h3>
            <p>把边界写清楚，不靠模糊表达制造可信感。</p>
          </div>
        </header>
        <div class="boundary-grid">
          <article v-for="group in boundaryGroups" :key="group.title" class="soft-card boundary-card">
            <strong>{{ group.title }}</strong>
            <ul class="bullet-list compact-list">
              <li v-for="item in group.items" :key="item">{{ item }}</li>
            </ul>
          </article>
        </div>
      </article>

      <article class="panel section">
        <header class="section-head">
          <div>
            <h3>状态覆盖</h3>
            <p>不是只识别跌倒，而是识别完整动作过程。</p>
          </div>
        </header>
        <div class="state-grid">
          <article v-for="item in stateCards" :key="item.code" class="soft-card state-card">
            <strong>{{ item.label }}</strong>
            <p>{{ capabilityNotes[item.code] || '系统会把这一类状态纳入连续判断。' }}</p>
          </article>
        </div>
      </article>

      <article class="panel section">
        <header class="section-head">
          <div>
            <h3>运行约束</h3>
            <p>这些约束直接影响误报控制和解释能力。</p>
          </div>
        </header>
        <ul class="bullet-list">
          <li v-for="item in qualityControls" :key="item">{{ item }}</li>
        </ul>
      </article>

      <article class="panel section full-span tech-section">
        <header class="section-head">
          <div>
            <h3>系统如何工作</h3>
            <p>主链保持清楚，技术细节放到第二层，不把系统说明页做成文档搬运页。</p>
          </div>
        </header>

        <div class="module-grid">
          <article v-for="module in moduleCards" :key="module.name" class="soft-card module-card">
            <strong>{{ module.name }}</strong>
            <p>{{ module.summary }}</p>
          </article>
        </div>

        <details class="tech-drawer">
          <summary>展开运行规格与版本口径</summary>
          <div class="facts-grid">
            <article v-for="item in runtimeFacts" :key="item.label" class="soft-card fact-card">
              <small>{{ item.label }}</small>
              <strong>{{ item.value }}</strong>
            </article>
          </div>

          <div class="tech-notes">
            <article class="soft-card note-card">
              <strong>当前运行口径</strong>
              <p>运行主干以稳定性优先，不因为某一轮实验分数更高就直接替换线上版本。</p>
            </article>
            <article class="soft-card note-card">
              <strong>评估方式</strong>
              <p>模型和系统同时看窗口级、样本级和应用级结果，避免只追单一指标。</p>
            </article>
          </div>
        </details>
      </article>
    </section>
  </section>
</template>

<style scoped>
.system-page {
  display: grid;
  gap: 18px;
}

.panel {
  border-radius: 28px;
  background: rgba(8, 16, 28, 0.82);
  box-shadow: inset 0 0 0 1px rgba(126, 149, 178, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 24px;
  padding: 28px;
}

.hero-copy {
  display: grid;
  gap: 12px;
  align-content: start;
}

.hero-copy small {
  color: rgba(193, 209, 226, 0.62);
  font-size: 12px;
  letter-spacing: 0.06em;
}

.hero-copy h2 {
  margin: 0;
  font-size: clamp(34px, 4vw, 50px);
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

.hero-stats,
.story-grid,
.boundary-grid,
.module-grid,
.state-grid,
.trust-grid,
.facts-grid,
.tech-notes {
  display: grid;
  gap: 14px;
}

.hero-stats {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0;
}

.stat-card,
.soft-card {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.03);
}

.stat-card {
  display: grid;
  gap: 8px;
  padding: 18px;
}

.stat-card dt,
.fact-card small {
  color: rgba(193, 209, 226, 0.58);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.stat-card dd,
.fact-card strong {
  margin: 0;
  font-size: 24px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.stat-card span {
  color: rgba(214, 226, 238, 0.72);
  font-size: 13px;
  line-height: 1.55;
}

.section {
  padding: 24px;
}

.intro-section {
  padding-top: 22px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  margin-bottom: 16px;
}

.section-head h3 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
}

.section-head p {
  margin: 8px 0 0;
  color: rgba(193, 209, 226, 0.7);
  font-size: 13px;
}

.story-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.story-card,
.boundary-card,
.module-card,
.state-card,
.trust-card,
.fact-card,
.note-card {
  padding: 18px;
}

.story-card strong,
.boundary-card strong,
.module-card strong,
.state-card strong,
.trust-card strong,
.note-card strong {
  display: block;
  margin-bottom: 10px;
  font-size: 18px;
  letter-spacing: -0.03em;
}

.story-card p,
.module-card p,
.state-card p,
.trust-card p,
.note-card p {
  margin: 0;
  color: rgba(214, 226, 238, 0.76);
  font-size: 14px;
  line-height: 1.7;
}

.system-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.full-span {
  grid-column: 1 / -1;
}

.bullet-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 18px;
  color: rgba(228, 237, 246, 0.9);
  line-height: 1.7;
}

.compact-list {
  gap: 8px;
}

.boundary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.trust-grid,
.state-grid,
.facts-grid,
.tech-notes {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.module-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 14px;
}

.tech-drawer {
  display: grid;
  gap: 14px;
  margin-top: 8px;
}

.tech-drawer summary {
  cursor: pointer;
  list-style: none;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.02);
  color: rgba(231, 239, 246, 0.92);
  font-weight: 700;
}

.tech-drawer summary::-webkit-details-marker {
  display: none;
}

.fact-card {
  display: grid;
  gap: 8px;
}

@media (max-width: 1180px) {
  .hero,
  .hero-stats,
  .story-grid,
  .system-layout,
  .boundary-grid,
  .module-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .trust-grid,
  .state-grid,
  .facts-grid,
  .tech-notes {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero,
  .section {
    padding: 16px;
    border-radius: 22px;
  }

  .hero-copy h2 {
    font-size: 30px;
  }

  .section-head h3 {
    font-size: 20px;
  }

  .stat-card dd,
  .fact-card strong {
    font-size: 20px;
  }
}
</style>
