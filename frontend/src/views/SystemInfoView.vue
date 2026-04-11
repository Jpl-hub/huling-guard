<script setup lang="ts">
import { computed } from 'vue'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk } from '../utils/presenters'

const store = useRuntimeStore()

const capabilityNotes: Record<string, string> = {
  normal: '系统持续确认当前是否安全。',
  near_fall: '发现明显失衡趋势，会先提醒尽快查看。',
  fall: '检测到跌倒，会直接进入高优先级提醒。',
  recovery: '确认人已经重新起身，用于判断是否恢复。',
  prolonged_lying: '长时间卧倒后单独升级，避免漏掉长卧风险。',
}

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
  ]
})

const topFacts = computed(() => {
  const meta = store.state.meta
  const profile = store.state.systemProfile?.runtime_profile
  return [
    {
      label: '当前输入',
      value: '实时视频 / 模拟监看 / 上传视频',
      detail: '三种接入方式都是真实可用的运行入口。',
    },
    {
      label: '连续判断',
      value: `${meta?.window_size ?? profile?.window_size ?? '-'} 帧时间窗`,
      detail: '不是只看某一帧，而是看一整段过程。',
    },
    {
      label: '历史留档',
      value: meta?.archive_enabled || profile?.archive_enabled ? '已开启' : '未开启',
      detail: '已经保存的过程可回看、复核和再训练。',
    },
  ]
})

const inputModes = computed(() => [
  {
    title: '实时视频接入',
    body: '接收连续视频帧，持续输出当前状态、提醒和时间线。',
  },
  {
    title: '模拟监看',
    body: '用固定机位样例流完整复现实时值守链路，用于演示和封闭环境测试。',
  },
  {
    title: '上传视频复核',
    body: '上传一段新视频，离线分析后生成完整过程、关键时刻和提醒记录。',
  },
])
</script>

<template>
  <section class="system-page">
    <section class="hero panel">
      <div class="hero-copy">
        <small>{{ store.state.systemProfile?.product_name || '护龄智守' }}</small>
        <h2>这套系统怎么接入、怎么判断、怎么留档</h2>
        <p>{{ store.state.systemProfile?.product_tagline || '单房间固定机位安全值守系统' }}</p>
      </div>
      <dl class="hero-facts">
        <div v-for="item in topFacts" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
          <span>{{ item.detail }}</span>
        </div>
      </dl>
    </section>

    <section class="system-layout">
      <article class="panel section">
        <header>
          <h3>系统替人完成什么</h3>
          <p>值守人员不需要一直盯屏，系统先把需要关注的过程挑出来。</p>
        </header>
        <ul class="goal-list">
          <li v-for="goal in store.state.systemProfile?.operational_goals ?? []" :key="goal">{{ goal }}</li>
        </ul>
      </article>

      <article class="panel section">
        <header>
          <h3>系统怎么形成判断</h3>
          <p>从视频输入到提醒生成，再到回看留档，是一条完整闭环。</p>
        </header>
        <div class="pipeline">
          <div
            v-for="module in store.state.systemProfile?.system_modules ?? []"
            :key="module.name"
            class="pipeline-step"
          >
            <strong>{{ module.name }}</strong>
            <p>{{ module.summary }}</p>
          </div>
        </div>
      </article>

      <article class="panel section">
        <header>
          <h3>当前支持哪些输入</h3>
          <p>这三种输入形态都是真实存在的系统入口，不是示意页面。</p>
        </header>
        <div class="input-grid">
          <div v-for="item in inputModes" :key="item.title" class="state-card">
            <strong>{{ item.title }}</strong>
            <span>{{ item.body }}</span>
          </div>
        </div>
      </article>

      <article class="panel section">
        <header>
          <h3>系统会关注哪些状态</h3>
          <p>不是只识别跌倒，而是识别完整动作过程。</p>
        </header>
        <div class="state-grid">
          <div
            v-for="item in store.state.systemProfile?.detectable_states ?? []"
            :key="item.code"
            class="state-card"
          >
            <strong>{{ item.label }}</strong>
            <span>{{ capabilityNotes[item.code] || '系统会把这一类状态纳入连续判断。' }}</span>
          </div>
        </div>
      </article>

      <article class="panel section">
        <header>
          <h3>系统如何收敛误报</h3>
          <p>重点不在模型名字，而在系统如何控制错误判断。</p>
        </header>
        <ul class="goal-list">
          <li v-for="item in store.state.systemProfile?.quality_controls ?? []" :key="item">{{ item }}</li>
        </ul>
      </article>

      <article class="panel section full-span">
        <header>
          <h3>当前运行口径</h3>
          <p>这里只保留真正会影响运行结果的关键参数。</p>
        </header>
        <div class="facts-grid">
          <article v-for="item in runtimeFacts" :key="item.label" class="fact-item">
            <small>{{ item.label }}</small>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
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
  border-radius: 30px;
  background: rgba(8, 17, 30, 0.76);
  backdrop-filter: blur(16px);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 24px;
  padding: 28px;
}

.hero-copy small {
  display: block;
  margin-bottom: 12px;
  color: rgba(199, 214, 231, 0.58);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.hero-copy h2 {
  margin: 0 0 12px;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.hero-copy p {
  margin: 0;
  color: rgba(199, 214, 231, 0.76);
  font-size: 15px;
}

.hero-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}

.hero-facts div {
  display: grid;
  gap: 8px;
  padding-left: 14px;
  border-left: 1px solid rgba(120, 146, 176, 0.14);
}

.hero-facts dt,
.fact-item small {
  color: rgba(199, 214, 231, 0.58);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.hero-facts dd,
.fact-item strong {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

.hero-facts span {
  color: rgba(199, 214, 231, 0.72);
  font-size: 12px;
  line-height: 1.5;
}

.system-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.section {
  padding: 22px;
}

.full-span {
  grid-column: 1 / -1;
}

.section header {
  margin-bottom: 16px;
}

.section h3 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.section p {
  margin: 8px 0 0;
  color: rgba(199, 214, 231, 0.68);
  font-size: 13px;
}

.goal-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 18px;
  color: rgba(225, 235, 246, 0.86);
  line-height: 1.65;
}

.pipeline {
  display: grid;
  gap: 12px;
}

.pipeline-step,
.state-card,
.fact-item {
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.02);
}

.pipeline-step strong,
.state-card strong {
  display: block;
  margin-bottom: 8px;
  font-size: 16px;
}

.pipeline-step p,
.state-card span {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.55;
}

.state-grid,
.input-grid,
.facts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1080px) {
  .hero,
  .hero-facts,
  .system-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .state-grid,
  .input-grid,
  .facts-grid {
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
    font-size: 28px;
  }

  .hero-facts {
    grid-template-columns: 1fr;
  }
}
</style>
