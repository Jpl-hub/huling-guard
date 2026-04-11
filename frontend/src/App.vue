<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppTopNav from './components/AppTopNav.vue'
import ModeSwitch from './components/ModeSwitch.vue'
import { useRuntimeStore } from './composables/useRuntimeStore'

const store = useRuntimeStore()
const route = useRoute()

const pageTitle = computed(() => String(route.meta.title ?? '实时值守'))
const pageHint = computed(() =>
  route.path === '/records'
    ? '查看留档过程与关键时刻。'
    : route.path === '/system'
      ? '查看接入方式、判断主链和运行口径。'
      : '查看当前状态、最近变化和处理建议。',
)
const modeModel = computed({
  get: () => store.state.mode,
  set: (value) => store.setMode(value),
})

onMounted(() => {
  store.startPolling()
})

onBeforeUnmount(() => {
  store.stopPolling()
})
</script>

<template>
  <div class="shell" :data-mode="store.state.mode">
    <AppTopNav />

    <div class="main">
      <header class="context-bar">
        <div class="context-copy">
          <span class="context-label">{{ pageTitle }}</span>
          <p>{{ pageHint }}</p>
        </div>

        <div class="page-actions">
          <ModeSwitch v-model="modeModel" />
          <div class="service-pill" :data-ok="store.state.health?.status === 'ok'">
            <strong>{{ store.state.health?.status === 'ok' ? '运行正常' : '等待连接' }}</strong>
            <span>{{ store.state.lastUpdatedAt || '尚未同步' }}</span>
          </div>
        </div>
      </header>

      <div v-if="store.state.errorMessage" class="error-banner">
        {{ store.state.errorMessage }}
      </div>

      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  background: var(--color-bg);
}

.main {
  width: min(100%, var(--page-max-width));
  margin: 0 auto;
  padding: var(--space-5) var(--space-6) var(--space-8);
}

.context-bar {
  display: flex;
  justify-content: space-between;
  gap: var(--space-6);
  align-items: flex-end;
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-line-soft);
}

.context-label {
  display: block;
  color: var(--color-text-primary);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.context-copy p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.page-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
}

.service-pill {
  display: grid;
  gap: var(--space-1);
  min-width: 152px;
  padding: 10px 0 10px var(--space-4);
  border-left: 1px solid var(--color-line-strong);
  background: transparent;
}

.service-pill strong {
  font-size: 14px;
}

.service-pill span {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.service-pill[data-ok='true'] strong {
  color: var(--color-ok);
}

.error-banner {
  margin-bottom: var(--space-5);
  padding: 14px 0 0;
  border-top: 1px solid rgba(255, 140, 144, 0.28);
  color: #ffd6d3;
  font-size: 14px;
}

@media (max-width: 1080px) {
  .main {
    padding: var(--space-5) var(--space-5) var(--space-7);
  }

  .context-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .service-pill {
    padding-left: 0;
    border-left: 0;
  }
}

@media (max-width: 640px) {
  .main {
    padding: var(--space-4) var(--space-4) var(--space-6);
  }

  .context-label {
    font-size: 20px;
  }

  .context-copy p {
    font-size: 12px;
  }

  .page-actions {
    width: 100%;
  }

  .service-pill {
    width: 100%;
    border-top: 1px solid var(--color-line-soft);
    padding-top: 12px;
  }
}
</style>
