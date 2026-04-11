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
  background: #050b13;
}

.main {
  width: min(100%, 1600px);
  margin: 0 auto;
  padding: 18px 24px 40px;
}

.context-bar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  margin-bottom: 22px;
}

.context-label {
  display: block;
  color: rgba(241, 247, 252, 0.94);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.context-copy p {
  margin: 6px 0 0;
  color: rgba(205, 219, 235, 0.66);
  font-size: 13px;
}

.page-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.service-pill {
  display: grid;
  gap: 4px;
  min-width: 152px;
  padding: 10px 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
}

.service-pill strong {
  font-size: 14px;
}

.service-pill span {
  color: rgba(199, 214, 231, 0.64);
  font-size: 12px;
}

.service-pill[data-ok='true'] {
  background: rgba(54, 211, 153, 0.08);
}

.error-banner {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 94, 98, 0.18);
  background: rgba(255, 94, 98, 0.12);
  color: #ffd6d3;
  font-size: 14px;
}

@media (max-width: 1080px) {
  .main {
    padding: 20px 20px 32px;
  }

  .context-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .main {
    padding: 14px 14px 24px;
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
  }
}
</style>
