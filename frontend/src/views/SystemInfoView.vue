<script setup lang="ts">
import { computed } from 'vue'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk } from '../utils/presenters'

const store = useRuntimeStore()

const runtimeChips = computed(() => {
  const meta = store.state.meta
  const profile = store.state.systemProfile?.runtime_profile
  const thresholds = store.state.systemProfile?.thresholds
  return [
    `设备 ${meta?.device ?? profile?.device ?? '-'}`,
    `窗口 ${meta?.window_size ?? profile?.window_size ?? '-'}`,
    `步长 ${meta?.inference_stride ?? profile?.inference_stride ?? '-'}`,
    `特征 ${meta?.kinematic_feature_set ?? profile?.kinematic_feature_set ?? '-'}`,
    meta?.scene_prior_loaded || profile?.scene_prior_loaded ? '房间先验已加载' : '房间先验未加载',
    meta?.archive_enabled || profile?.archive_enabled ? '历史记录已启用' : '历史记录未启用',
    `跌倒阈值 ${formatRisk(thresholds?.fall)}`,
    `长卧阈值 ${formatRisk(thresholds?.prolonged_lying)}`,
  ]
})
</script>

<template>
  <section class="system-page">
    <section class="hero panel">
      <div class="hero-copy">
        <small>Runtime</small>
        <h2>{{ store.state.systemProfile?.product_name || '护龄智守' }}</h2>
        <p>{{ store.state.systemProfile?.product_tagline || '单房间固定摄像头安全值守系统' }}</p>
      </div>
      <div class="hero-users">
        <span v-for="user in store.state.systemProfile?.target_users ?? []" :key="user">
          {{ user }}
        </span>
      </div>
    </section>

    <section class="system-layout">
      <article class="panel section">
        <header>
          <h3>使用目标</h3>
        </header>
        <ul class="goal-list">
          <li v-for="goal in store.state.systemProfile?.operational_goals ?? []" :key="goal">{{ goal }}</li>
        </ul>
      </article>

      <article class="panel section">
        <header>
          <h3>识别链路</h3>
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
          <h3>可识别状态</h3>
        </header>
        <div class="state-grid">
          <div
            v-for="item in store.state.systemProfile?.detectable_states ?? []"
            :key="item.code"
            class="state-card"
          >
            <strong>{{ item.label }}</strong>
            <span>{{ item.code }}</span>
          </div>
        </div>
      </article>

      <article class="panel section">
        <header>
          <h3>当前部署</h3>
        </header>
        <div class="chips">
          <span v-for="chip in runtimeChips" :key="chip" class="chip">{{ chip }}</span>
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
  border-radius: 28px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(8, 17, 30, 0.76);
  backdrop-filter: blur(16px);
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding: 26px 28px;
}

.hero-copy small {
  display: inline-block;
  margin-bottom: 10px;
  color: rgba(143, 181, 221, 0.76);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.hero-copy h2 {
  margin: 0 0 8px;
  font-size: clamp(30px, 4vw, 44px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.hero-copy p {
  margin: 0;
  color: rgba(199, 214, 231, 0.76);
}

.hero-users {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-users span,
.chip {
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(120, 146, 176, 0.18);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(225, 235, 246, 0.84);
  font-size: 13px;
}

.system-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.section {
  padding: 22px;
}

.section header {
  margin-bottom: 16px;
}

.section h3 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
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
.state-card {
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid rgba(120, 146, 176, 0.14);
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

.state-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 1080px) {
  .system-layout {
    grid-template-columns: 1fr;
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 720px) {
  .state-grid {
    grid-template-columns: 1fr;
  }
}
</style>
