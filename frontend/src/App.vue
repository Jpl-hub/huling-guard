<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppTopNav from './components/AppTopNav.vue'
import ModeSwitch from './components/ModeSwitch.vue'
import { useRuntimeStore } from './composables/useRuntimeStore'

const store = useRuntimeStore()
const route = useRoute()

const pageTitle = computed(() => String(route.meta.title ?? '实时值守'))
const pageSubtitle = computed(() => String(route.meta.subtitle ?? ''))

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
      <header class="page-head">
        <div class="page-copy">
          <h1>{{ pageTitle }}</h1>
          <p v-if="pageSubtitle">{{ pageSubtitle }}</p>
        </div>

        <div class="page-actions">
          <ModeSwitch v-model="modeModel" />
          <div class="service-pill" :data-ok="store.state.health?.status === 'ok'">
            <strong>{{ store.state.health?.status === 'ok' ? '服务在线' : '等待连接' }}</strong>
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
  background:
    radial-gradient(circle at top left, rgba(53, 124, 255, 0.2), transparent 22%),
    radial-gradient(circle at right, rgba(67, 215, 255, 0.1), transparent 28%),
    #050b13;
}

.main {
  width: min(100%, 1520px);
  margin: 0 auto;
  padding: 28px 28px 40px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  margin-bottom: 24px;
}

.page-copy h1 {
  margin: 0 0 8px;
  font-size: clamp(30px, 4vw, 44px);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.page-copy p {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.5;
}

.page-actions {
  display: grid;
  gap: 10px;
  justify-items: end;
}

.service-pill {
  display: grid;
  gap: 4px;
  min-width: 152px;
  padding: 10px 14px;
  border-radius: 20px;
  border: 1px solid rgba(120, 146, 176, 0.18);
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
  border-color: rgba(54, 211, 153, 0.24);
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

  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-actions {
    width: 100%;
    justify-items: start;
  }
}
</style>
