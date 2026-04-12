<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import AppTopNav from './components/AppTopNav.vue'
import { useRuntimeStore } from './composables/useRuntimeStore'
import { formatPercent, formatTimestamp, incidentLabel, stateTone } from './utils/presenters'

const store = useRuntimeStore()
const route = useRoute()
const router = useRouter()

const pageTitle = computed(() => String(route.meta.title ?? '实时值守'))
const pageHint = computed(() =>
  route.path === '/matrix'
    ? '查看监视器、输入状态和风险分布。'
    : route.path === '/records'
      ? '检索、筛选并回看已保存过程。'
      : route.path === '/brief'
        ? '汇总留档、提醒和重点复核记录。'
        : route.path === '/system'
        ? '查看处理管线、阈值和质量控制。'
        : '查看当前状态、最近变化和处理建议。',
)
const managementOpen = ref(false)
const alertMuted = ref(false)
const audioUnlocked = ref(false)
const lastAlertKey = ref('')
let audioContext: AudioContext | null = null

const uploadSources = computed(() =>
  store.state.demoVideos.filter((item) => item.source_kind === 'upload'),
)
const uploadSourceCount = computed(() => uploadSources.value.length)
const processingUploadCount = computed(() =>
  uploadSources.value.filter((item) => item.processing_status === 'processing').length,
)
const removableUploadCount = computed(() =>
  uploadSources.value.filter((item) => item.processing_status !== 'processing').length,
)
const archiveCount = computed(() => Number(store.state.archiveSummary?.archive_total ?? 0))
const quietArchiveCount = computed(() =>
  Math.max(archiveCount.value - Number(store.state.archiveSummary?.sessions_with_incidents ?? 0), 0),
)
const latestIncident = computed(() => store.displayIncidents.value[0] ?? store.displayState.value.lastIncident)

const globalAlert = computed(() => {
  const display = store.displayState.value
  if (!display.ready) {
    return null
  }
  const tone = stateTone(display.predictedState, display.riskScore)
  if (tone === 'safe' && display.incidentTotal <= 0) {
    return null
  }
  return {
    tone,
    title: tone === 'alert' ? '高风险事件正在持续' : '当前存在需要留意的风险变化',
    action: tone === 'alert' ? '进入实时值守立即核查' : '进入实时值守继续观察',
    detail: latestIncident.value
      ? `${incidentLabel(latestIncident.value.kind)} · ${formatTimestamp(latestIncident.value.timestamp)} · 当前风险 ${formatPercent(display.riskScore, 1)}`
      : `${store.verdict.value.detail} · 当前风险 ${formatPercent(display.riskScore, 1)}`,
  }
})

const alertStatusText = computed(() => {
  if (store.state.liveSource?.available) {
    return '实时接入中'
  }
  if (store.state.liveIngest?.active) {
    return '实时接入任务运行中'
  }
  return uploadSourceCount.value > 0 ? '上传视频与模拟监看并存' : '当前以模拟监看为主'
})

const soundLabel = computed(() => (alertMuted.value ? '警报音已静音' : '警报音已开启'))

async function ensureAudioUnlocked(): Promise<void> {
  audioUnlocked.value = true
  const AudioCtor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioCtor) {
    return
  }
  if (!audioContext) {
    audioContext = new AudioCtor()
  }
  if (audioContext.state === 'suspended') {
    await audioContext.resume().catch(() => undefined)
  }
}

function playAlertTone(): void {
  if (alertMuted.value || !audioUnlocked.value) {
    return
  }
  const AudioCtor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioCtor) {
    return
  }
  if (!audioContext) {
    audioContext = new AudioCtor()
  }
  if (audioContext.state === 'suspended') {
    return
  }
  const ctx = audioContext
  const start = ctx.currentTime + 0.02
  const oscillator = ctx.createOscillator()
  const gain = ctx.createGain()
  oscillator.type = 'triangle'
  oscillator.frequency.setValueAtTime(880, start)
  oscillator.frequency.exponentialRampToValueAtTime(660, start + 0.16)
  gain.gain.setValueAtTime(0.0001, start)
  gain.gain.exponentialRampToValueAtTime(0.055, start + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.2)
  oscillator.connect(gain)
  gain.connect(ctx.destination)
  oscillator.start(start)
  oscillator.stop(start + 0.22)
}

function persistMute(value: boolean): void {
  alertMuted.value = value
  window.localStorage.setItem('huling-guard-alert-muted', value ? '1' : '0')
}

function openLive(): void {
  void router.push('/live')
}

function openRecords(): void {
  void router.push('/records')
}

function openBrief(): void {
  void router.push('/brief')
}

function openMatrix(): void {
  void router.push('/matrix')
}

function triggerRefresh(): void {
  void store.refresh()
}

function clearUploads(): void {
  if (!removableUploadCount.value) {
    return
  }
  if (!window.confirm(`确定要清理 ${removableUploadCount.value} 路可移除上传源吗？已被留档引用的视频会自动保留。`)) {
    return
  }
  void store.clearRemovableUploadSources()
}

function clearQuietRecords(): void {
  if (!quietArchiveCount.value) {
    return
  }
  if (!window.confirm(`确定要清理 ${quietArchiveCount.value} 条无提醒留档吗？`)) {
    return
  }
  void store.clearQuietArchives()
}

function handleFirstInteraction(): void {
  void ensureAudioUnlocked()
}

watch(
  () => {
    const alert = globalAlert.value
    if (!alert || alert.tone !== 'alert') {
      return ''
    }
    return `${store.displayState.value.predictedState ?? 'unknown'}:${latestIncident.value?.timestamp ?? store.displayReport.value?.peak_risk?.timestamp ?? 'none'}`
  },
  (nextKey) => {
    if (!nextKey || nextKey === lastAlertKey.value) {
      return
    }
    lastAlertKey.value = nextKey
    playAlertTone()
  },
)

onMounted(() => {
  alertMuted.value = window.localStorage.getItem('huling-guard-alert-muted') === '1'
  window.addEventListener('pointerdown', handleFirstInteraction, { passive: true })
  window.addEventListener('keydown', handleFirstInteraction)
  store.startPolling()
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', handleFirstInteraction)
  window.removeEventListener('keydown', handleFirstInteraction)
  store.stopPolling()
  if (audioContext && audioContext.state !== 'closed') {
    void audioContext.close().catch(() => undefined)
  }
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
          <a-button size="large" @click="managementOpen = true">运行管理</a-button>
          <div class="service-pill" :data-ok="store.state.health?.status === 'ok'">
            <strong>{{ store.state.health?.status === 'ok' ? '运行正常' : '等待连接' }}</strong>
            <span>{{ store.state.lastUpdatedAt || '尚未同步' }}</span>
          </div>
        </div>
      </header>

      <section v-if="globalAlert" class="global-alert" :data-tone="globalAlert.tone">
        <div class="alert-copy">
          <small>{{ globalAlert.tone === 'alert' ? '跨页面警报' : '跨页面提醒' }}</small>
          <strong>{{ globalAlert.title }}</strong>
          <p>{{ globalAlert.detail }}</p>
        </div>
        <div class="alert-actions">
          <button type="button" class="alert-ghost" @click="persistMute(!alertMuted)">
            {{ soundLabel }}
          </button>
          <button type="button" class="alert-primary" @click="openLive">
            {{ globalAlert.action }}
          </button>
        </div>
      </section>

      <div v-if="store.state.errorMessage" class="error-banner">
        {{ store.state.errorMessage }}
      </div>

      <RouterView />
    </div>

    <a-drawer
      v-model:visible="managementOpen"
      width="380"
      unmount-on-close
      :footer="false"
      title="运行管理"
    >
      <div class="drawer-body">
        <section class="drawer-section">
          <header>
            <strong>当前运行态</strong>
            <span>{{ alertStatusText }}</span>
          </header>
          <div class="drawer-stats">
            <article>
              <small>上传源</small>
              <strong>{{ uploadSourceCount }}</strong>
              <span>{{ processingUploadCount ? `${processingUploadCount} 路分析中` : '当前无待处理上传' }}</span>
            </article>
            <article>
              <small>历史留档</small>
              <strong>{{ archiveCount }}</strong>
              <span>{{ archiveCount ? '可进入历史回看继续清理' : '尚无留档' }}</span>
            </article>
          </div>
        </section>

        <section class="drawer-section">
          <header>
            <strong>警报与交互</strong>
            <span>跨页面提醒与基础运行控制</span>
          </header>
          <label class="drawer-switch">
            <div>
              <strong>警报音提示</strong>
              <span>检测到高风险事件时尝试播放提示音。</span>
            </div>
            <a-switch :model-value="!alertMuted" @change="persistMute(!Boolean($event))" />
          </label>
        </section>

        <section class="drawer-section">
          <header>
            <strong>快捷操作</strong>
            <span>跨页面进入关键工作区</span>
          </header>
          <div class="drawer-actions">
            <a-button size="large" type="primary" @click="openLive">进入实时值守</a-button>
            <a-button size="large" @click="openRecords">查看历史回看</a-button>
            <a-button size="large" @click="openBrief">生成交接班简报</a-button>
            <a-button size="large" @click="openMatrix">返回监视器总览</a-button>
            <a-button size="large" @click="triggerRefresh">刷新全部状态</a-button>
          </div>
        </section>

        <section class="drawer-section">
          <header>
            <strong>存储清理</strong>
            <span>清理已分析完的上传源与无提醒留档</span>
          </header>
          <div class="drawer-stats cleanup-stats">
            <article>
              <small>可移除上传源</small>
              <strong>{{ removableUploadCount }}</strong>
              <span>{{ removableUploadCount ? '会自动保留已被留档引用的视频' : '当前没有可清理上传源' }}</span>
            </article>
            <article>
              <small>可清理普通留档</small>
              <strong>{{ quietArchiveCount }}</strong>
              <span>{{ quietArchiveCount ? '仅移除未触发正式提醒的留档' : '当前没有可清理普通留档' }}</span>
            </article>
          </div>
          <div class="drawer-actions cleanup-actions">
            <a-button
              size="large"
              :loading="store.state.bulkRemovingSources"
              :disabled="!removableUploadCount"
              @click="clearUploads"
            >
              清理可移除上传源
            </a-button>
            <a-button
              size="large"
              :loading="store.state.bulkRemovingArchives"
              :disabled="!quietArchiveCount"
              @click="clearQuietRecords"
            >
              清理无提醒留档
            </a-button>
          </div>
        </section>

        <section class="drawer-section subtle">
          <header>
            <strong>当前规则</strong>
          </header>
          <ul class="drawer-rules">
            <li>已被历史留档引用的上传视频不可直接删除。</li>
            <li>分析中的上传视频不可删除，避免任务和回放断裂。</li>
            <li>高风险提醒会在任意页面持续显示，直到状态回落。</li>
          </ul>
        </section>
      </div>
    </a-drawer>
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

.global-alert {
  position: sticky;
  top: 82px;
  z-index: 12;
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  align-items: center;
  margin-bottom: var(--space-5);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.02);
  box-shadow: inset 0 0 0 1px var(--color-line-soft), var(--shadow-soft);
  backdrop-filter: blur(10px);
}

.global-alert[data-tone='alert'] {
  box-shadow: inset 0 0 0 1px var(--color-alert-line), var(--shadow-alert);
}

.global-alert[data-tone='watch'] {
  box-shadow: inset 0 0 0 1px var(--color-watch-line), var(--shadow-watch);
}

.alert-copy {
  display: grid;
  gap: var(--space-1);
}

.alert-copy small {
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.alert-copy strong {
  font-size: 20px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.alert-copy p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.alert-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.alert-primary,
.alert-ghost {
  min-height: 40px;
  border-radius: 999px;
  padding: 0 16px;
  border: 0;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.alert-primary {
  background: var(--color-text-primary);
  color: var(--color-bg-strong);
}

.alert-ghost {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-secondary);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.error-banner {
  margin-bottom: var(--space-5);
  padding: 14px 0 0;
  border-top: 1px solid var(--color-alert-line);
  color: var(--color-text-alert);
  font-size: 14px;
}

.drawer-body {
  display: grid;
  gap: var(--space-5);
}

.drawer-section {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  box-shadow: inset 0 0 0 1px var(--color-line-soft);
}

.drawer-section.subtle {
  background: rgba(255, 255, 255, 0.02);
}

.drawer-section header {
  display: grid;
  gap: var(--space-1);
}

.drawer-section header strong {
  font-size: 16px;
  letter-spacing: -0.03em;
}

.drawer-section header span,
.drawer-switch span,
.drawer-stats span,
.drawer-rules li {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.drawer-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.drawer-stats article {
  display: grid;
  gap: var(--space-1);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line-soft);
}

.drawer-stats small {
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.drawer-stats strong {
  font-size: 26px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.drawer-switch {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: center;
}

.drawer-switch strong {
  display: block;
  font-size: 14px;
  margin-bottom: 2px;
}

.drawer-actions {
  display: grid;
  gap: var(--space-3);
}

.cleanup-stats {
  margin-top: calc(var(--space-2) * -1);
}

.cleanup-actions :deep(.arco-btn) {
  justify-content: flex-start;
}

.drawer-rules {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding: 0 0 0 var(--space-4);
}

@media (max-width: 1080px) {
  .main {
    padding: var(--space-5) var(--space-5) var(--space-7);
  }

  .context-bar,
  .global-alert,
  .drawer-switch {
    flex-direction: column;
    align-items: flex-start;
  }

  .service-pill {
    padding-left: 0;
    border-left: 0;
  }

  .alert-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .main {
    padding: var(--space-4) var(--space-4) var(--space-6);
  }

  .context-label {
    font-size: 20px;
  }

  .context-copy p,
  .alert-copy p {
    font-size: 12px;
  }

  .page-actions,
  .alert-actions,
  .drawer-stats {
    width: 100%;
  }

  .drawer-stats {
    grid-template-columns: 1fr;
  }

  .service-pill {
    width: 100%;
    border-top: 1px solid var(--color-line-soft);
    padding-top: 12px;
  }

  .global-alert {
    top: 74px;
  }
}
</style>
