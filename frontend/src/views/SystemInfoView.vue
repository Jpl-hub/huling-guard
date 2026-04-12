<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import { RadarComponent, TooltipComponent } from 'echarts/components'

import { useRuntimeStore } from '../composables/useRuntimeStore'
import { formatRisk } from '../utils/presenters'

use([CanvasRenderer, RadarChart, RadarComponent, TooltipComponent])

const store = useRuntimeStore()

const runtimeMeta = computed(() => store.state.meta)
const runtimeProfile = computed(() => store.state.systemProfile?.runtime_profile ?? null)
const runtimeSummary = computed(() => store.state.runtimeSummary)
const runtimeState = computed(() => store.state.runtimeState)
const thresholds = computed(() => store.state.systemProfile?.thresholds ?? {})

const deviceLabel = computed(() => runtimeMeta.value?.device ?? runtimeProfile.value?.device ?? '-')
const windowSizeLabel = computed(() => String(runtimeMeta.value?.window_size ?? runtimeProfile.value?.window_size ?? '-'))
const strideLabel = computed(() => String(runtimeMeta.value?.inference_stride ?? runtimeProfile.value?.inference_stride ?? '-'))
const featureSetLabel = computed(() => runtimeMeta.value?.kinematic_feature_set ?? runtimeProfile.value?.kinematic_feature_set ?? '-')
const windowSpanLabel = computed(() => {
  const span = runtimeState.value?.window_span_seconds ?? 0
  return span > 0 ? `${span.toFixed(1)} 秒` : '待汇入'
})
const deviceTone = computed(() => {
  const device = (deviceLabel.value || '').toLowerCase()
  if (device.includes('cuda') || device.includes('gpu')) return 'ok'
  if (device.includes('cpu')) return 'watch'
  return 'neutral'
})
const runtimeReady = computed(() => Boolean(runtimeSummary.value?.ready))

const telemetryItems = computed(() => [
  { label: '推理设备', value: deviceLabel.value, detail: deviceTone.value === 'ok' ? '已检测到加速设备' : '当前以运行时配置为准', tone: deviceTone.value },
  { label: '时序记忆', value: `${windowSizeLabel.value} 帧`, detail: windowSpanLabel.value, tone: 'neutral' },
  { label: '更新步长', value: `${strideLabel.value} 帧`, detail: '按连续时间窗更新', tone: 'neutral' },
  { label: '特征口径', value: featureSetLabel.value, detail: '骨架、运动学、场景关系联合输入', tone: 'neutral' },
  { label: '房间先验', value: runtimeMeta.value?.scene_prior_loaded || runtimeProfile.value?.scene_prior_loaded ? '已加载' : '未加载', detail: '用于区分床上躺卧与地面卧倒', tone: runtimeMeta.value?.scene_prior_loaded || runtimeProfile.value?.scene_prior_loaded ? 'ok' : 'watch' },
  { label: '历史归档', value: runtimeMeta.value?.archive_enabled || runtimeProfile.value?.archive_enabled ? '已开启' : '未开启', detail: '过程可保存、可复看、可复核', tone: runtimeMeta.value?.archive_enabled || runtimeProfile.value?.archive_enabled ? 'ok' : 'watch' },
])

const qualityAvailable = computed(() =>
  runtimeReady.value && Number(runtimeSummary.value?.observed_frames ?? runtimeState.value?.observed_frames ?? 0) > 0,
)

const qualityMeters = computed(() => {
  const quality = runtimeSummary.value?.data_quality ?? runtimeState.value?.data_quality
  const rows = [
    { label: '骨架质量', value: quality?.pose_quality_score ?? 0, detail: '评估当前骨架输入的整体可信度' },
    { label: '关键点均值', value: quality?.mean_keypoint_confidence ?? 0, detail: '反映关节检测的平均置信水平' },
    { label: '可见关节比例', value: quality?.visible_joint_ratio ?? 0, detail: '反映遮挡、低光和出框对输入的影响' },
  ]
  return rows.map((item) => ({
    ...item,
    value: qualityAvailable.value ? item.value : null,
    displayValue: qualityAvailable.value ? formatRisk(item.value) : '--',
    detail: qualityAvailable.value ? item.detail : '等待输入汇入',
  }))
})

const thresholdRadarOption = computed(() => ({
  animation: false,
  tooltip: {
    trigger: 'item',
    borderWidth: 0,
    backgroundColor: 'rgba(5, 14, 24, 0.94)',
    textStyle: { color: '#f5fbff' },
  },
  radar: {
    center: ['50%', '54%'],
    radius: '68%',
    splitNumber: 4,
    axisName: { color: 'rgba(214, 225, 237, 0.74)', fontSize: 12 },
    splitLine: { lineStyle: { color: 'rgba(120, 146, 176, 0.16)' } },
    splitArea: { areaStyle: { color: ['rgba(255,255,255,0.01)', 'rgba(255,255,255,0.02)'] } },
    axisLine: { lineStyle: { color: 'rgba(120, 146, 176, 0.14)' } },
    indicator: [
      { name: '失衡阈值', max: 1 },
      { name: '跌倒阈值', max: 1 },
      { name: '恢复阈值', max: 1 },
      { name: '长卧阈值', max: 1 },
    ],
  },
  series: [
    {
      type: 'radar',
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#79d4e7' },
      itemStyle: { color: '#79d4e7' },
      areaStyle: { color: 'rgba(121, 212, 231, 0.18)' },
      data: [
        {
          value: [
            thresholds.value.near_fall ?? 0,
            thresholds.value.fall ?? 0,
            thresholds.value.recovery ?? 0,
            thresholds.value.prolonged_lying ?? 0,
          ],
          name: '运行阈值',
        },
      ],
    },
  ],
}))

const thresholdFacts = computed(() => [
  { label: '失衡提醒', value: formatRisk(thresholds.value.near_fall) },
  { label: '跌倒确认', value: formatRisk(thresholds.value.fall) },
  { label: '恢复确认', value: formatRisk(thresholds.value.recovery) },
  { label: '长卧确认', value: formatRisk(thresholds.value.prolonged_lying) },
  { label: '长卧时长', value: thresholds.value.prolonged_lying_seconds ? `${thresholds.value.prolonged_lying_seconds.toFixed(1)} 秒` : '-' },
])

const pipelineNodes = computed(() => [
  { title: '视频源', body: '本机设备 / RTSP / 文件', metric: store.state.liveSource?.available ? '实时输入中' : '等待输入', tone: store.state.liveSource?.available ? 'ok' : 'neutral' },
  { title: 'RTMO 姿态', body: '17 点骨架与置信度', metric: qualityMeters.value[1]?.value !== null ? `均值 ${qualityMeters.value[1].displayValue}` : '等待骨架', tone: runtimeReady.value ? 'ok' : 'watch' },
  { title: '时序网络', body: `窗口 ${windowSizeLabel.value} / 步长 ${strideLabel.value}`, metric: runtimeSummary.value?.predicted_state ? `当前 ${runtimeSummary.value.predicted_state}` : '等待正式结论', tone: runtimeReady.value ? 'ok' : 'watch' },
  { title: '事件引擎', body: '提醒、跌倒、长卧、恢复', metric: runtimeSummary.value?.incident_total ? `${runtimeSummary.value.incident_total} 条事件` : '尚无事件', tone: (runtimeSummary.value?.incident_total ?? 0) > 0 ? 'watch' : 'neutral' },
])

const stateCards = computed(() => (store.state.systemProfile?.detectable_states ?? []).map((item) => ({
  ...item,
  note:
    item.code === 'normal'
      ? '建立正常活动基线，降低日常动作误报。'
      : item.code === 'near_fall'
        ? '识别明显失衡趋势，用于提前提示。'
        : item.code === 'fall'
          ? '识别跌倒过程并触发高优先级提醒。'
          : item.code === 'recovery'
            ? '识别异常后的起身恢复过程。'
            : '识别持续低位停留并升级长卧风险。',
})))

const qualityControls = computed(() => store.state.systemProfile?.quality_controls ?? [])
const boundaryGroups = computed(() => [
  {
    title: '适合的场景',
    items: ['单房间、固定机位、连续值守。', '重点判断是否安全、是否需要立即查看。', '需要过程留档和后续复核。'],
  },
  {
    title: '接入方式',
    items: ['本机摄像头或系统可见的视频设备。', 'RTSP 视频流。', '本地视频文件。'],
  },
  {
    title: '当前边界',
    items: ['不主打多路集中调度。', '不主打移动机位和频繁变焦。', '不能直接接入封闭型纯云摄像头。'],
  },
])
</script>

<template>
  <section class="system-page">
    <header class="page-head">
      <div class="page-copy">
        <div>
          <small class="eyebrow">{{ store.state.systemProfile?.product_name || '护龄智守' }}</small>
          <h2>运行主链与场景感知</h2>
        </div>
        <p>固定机位视频先经 RTMO 提取骨架，再进入时序网络和事件引擎，输出连续状态、风险等级与可复核过程。</p>
        <ul class="page-points">
          <li>RTMO 负责骨架提取与输入质量门控。</li>
          <li>时序网络负责连续动作状态判断。</li>
          <li>事件引擎负责提醒升级、归档与复核。</li>
        </ul>
      </div>

      <div class="page-scene">
        <div class="scene-shell" :data-ready="runtimeReady">
          <svg class="scene-svg" viewBox="0 0 640 420" aria-hidden="true">
            <path class="room-line" d="M200 95H440V245H200Z" />
            <path class="room-line" d="M200 95L120 180H520L440 95" />
            <path class="room-line" d="M200 245L120 330H520L440 245" />
            <path class="room-line" d="M120 180V330" />
            <path class="room-line" d="M520 180V330" />
            <path class="room-line" d="M200 95L200 245" />
            <path class="room-line" d="M440 95V245" />
            <path class="zone-bed" d="M154 286L248 286L286 244L202 244Z" />
            <path class="zone-floor" d="M272 280L388 280L430 244L314 244Z" />
            <path class="flow-line" d="M48 212C120 212 174 214 248 242" />
            <path class="flow-line" d="M392 242C468 214 522 198 600 198" />
            <circle class="subject-ring" cx="320" cy="248" r="26" />
            <circle class="subject-core" cx="320" cy="248" r="10" />
          </svg>

          <div class="scene-tag tag-input">
            <strong>输入层</strong>
            <span>摄像头 / RTSP / 视频文件</span>
          </div>
          <div class="scene-tag tag-pose">
            <strong>姿态层</strong>
            <span>RTMO 骨架与质量门控</span>
          </div>
          <div class="scene-tag tag-engine">
            <strong>决策层</strong>
            <span>时序网络 + 事件引擎</span>
          </div>
        </div>
      </div>
    </header>

    <section class="telemetry-strip">
      <article v-for="item in telemetryItems" :key="item.label" class="telemetry-item">
        <small>{{ item.label }}</small>
        <strong class="telemetry-value">{{ item.value }}</strong>
        <span class="telemetry-detail" :data-tone="item.tone">
          <i v-if="item.tone !== 'neutral'" class="status-dot" :data-tone="item.tone" />
          {{ item.detail }}
        </span>
      </article>
    </section>

    <section class="section-block">
      <header class="section-head">
        <h3>运行链路</h3>
        <p>实时展示系统当前的处理管线与节点流转状态。</p>
      </header>
      <div class="pipeline-track" :data-ready="runtimeReady">
        <div v-for="(node, index) in pipelineNodes" :key="node.title" class="pipeline-node" :data-tone="node.tone">
          <small>{{ `0${index + 1}` }}</small>
          <strong>{{ node.title }}</strong>
          <span>{{ node.body }}</span>
          <em>{{ node.metric }}</em>
        </div>
      </div>
    </section>

    <section class="section-block state-block">
      <header class="section-head">
        <h3>识别状态</h3>
        <p>展示系统支持的状态类型与对应的处置语义。</p>
      </header>
      <div class="state-list state-grid">
        <article v-for="item in stateCards" :key="item.code" class="line-row">
          <strong>{{ item.label }}</strong>
          <p>{{ item.note }}</p>
        </article>
      </div>
    </section>

    <section class="section-grid metrics-grid">
      <section class="section-block">
        <header class="section-head">
          <h3>当前质量面板</h3>
          <p>展示当前骨架输入质量，用于辅助判断结果可信度。</p>
        </header>
        <div class="quality-list">
          <article v-for="item in qualityMeters" :key="item.label" class="quality-item">
            <div class="quality-head">
              <strong>{{ item.label }}</strong>
              <span class="telemetry-value" :data-empty="item.value === null">{{ item.displayValue }}</span>
            </div>
            <div class="quality-bar" :data-empty="item.value === null" aria-hidden="true">
              <span :style="{ width: item.value === null ? '0%' : `${Math.max(0, Math.min(100, item.value * 100))}%` }" />
            </div>
            <p>{{ item.detail }}</p>
          </article>
        </div>
      </section>

      <section class="section-block">
        <header class="section-head">
          <h3>运行阈值雷达</h3>
          <p>系统依据预设的安全基线触发自动预警。</p>
        </header>
        <div class="radar-shell">
          <VChart :option="thresholdRadarOption" autoresize class="radar-chart" />
        </div>
        <div class="threshold-list">
          <article v-for="item in thresholdFacts" :key="item.label">
            <small>{{ item.label }}</small>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>
    </section>

    <section class="section-block boundary-block">
      <header class="section-head">
        <h3>质量控制与边界</h3>
        <p>展示当前适用场景、接入方式与运行边界。</p>
      </header>
      <div class="boundary-grid">
        <section v-for="group in boundaryGroups" :key="group.title" class="boundary-group">
          <h4>{{ group.title }}</h4>
          <ul>
            <li v-for="item in group.items" :key="item">{{ item }}</li>
          </ul>
        </section>
      </div>
      <ul class="control-list">
        <li v-for="item in qualityControls" :key="item">{{ item }}</li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.system-page {
  display: grid;
  gap: var(--space-6);
}

.page-head {
  display: grid;
  grid-template-columns: minmax(0, 0.86fr) minmax(420px, 0.94fr);
  gap: var(--space-6);
  align-items: stretch;
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-line-soft);
}

.page-head h2 {
  margin: var(--space-1) 0 0;
  font-size: clamp(30px, 4vw, 46px);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

.page-copy {
  display: grid;
  align-content: start;
  gap: var(--space-4);
}

.page-copy p {
  max-width: 40ch;
}

.page-points {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.page-points li {
  position: relative;
  padding-left: 16px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.page-points li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--color-accent);
  box-shadow: 0 0 0 6px rgba(121, 212, 231, 0.08);
}

.page-scene {
  display: flex;
  align-items: stretch;
}

.scene-shell {
  position: relative;
  width: 100%;
  min-height: 340px;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.02);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}

.scene-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.18;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.88), transparent 90%);
}

.scene-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.room-line,
.flow-line,
.zone-bed,
.zone-floor,
.subject-ring,
.subject-core {
  fill: none;
  vector-effect: non-scaling-stroke;
}

.room-line {
  stroke: rgba(121, 212, 231, 0.34);
  stroke-width: 1.6;
}

.flow-line {
  stroke: rgba(121, 212, 231, 0.56);
  stroke-width: 2;
  stroke-dasharray: 10 12;
  opacity: 0.42;
}

.scene-shell[data-ready='true'] .flow-line {
  animation: dash-flow 3.2s linear infinite;
  opacity: 0.92;
}

.zone-bed {
  fill: rgba(121, 212, 231, 0.08);
  stroke: rgba(121, 212, 231, 0.38);
  stroke-width: 1.4;
}

.zone-floor {
  fill: rgba(255, 172, 92, 0.08);
  stroke: rgba(255, 172, 92, 0.42);
  stroke-width: 1.4;
}

.subject-ring {
  stroke: rgba(121, 212, 231, 0.56);
  stroke-width: 1.6;
  transform-origin: center;
  animation: pulse-ring 2.4s ease-in-out infinite;
}

.subject-core {
  fill: rgba(121, 212, 231, 0.95);
  filter: drop-shadow(0 0 10px rgba(121, 212, 231, 0.4));
}

.scene-tag {
  position: absolute;
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(5, 14, 24, 0.78);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(8px);
}

.scene-tag strong {
  font-size: 13px;
  letter-spacing: -0.02em;
}

.scene-tag span {
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.tag-input {
  top: 18px;
  left: 18px;
  max-width: 220px;
}

.tag-pose {
  left: 46%;
  bottom: 22px;
  transform: translateX(-50%);
  min-width: 220px;
}

.tag-engine {
  top: 52px;
  right: 18px;
  max-width: 220px;
}


.page-head p,
.section-head p,
.line-row p,
.boundary-group li,
.quality-item p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.eyebrow,
.telemetry-item small,
.threshold-list small,
.pipeline-node small {
  color: var(--color-text-tertiary);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.telemetry-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-4);
}

.telemetry-item {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-line-soft);
}

.telemetry-value {
  font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
  font-size: 22px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.telemetry-detail {
  display: inline-flex;
  gap: var(--space-2);
  align-items: center;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 6px rgba(255,255,255,0.03);
  animation: pulse 1.8s ease-in-out infinite;
}

.telemetry-detail[data-tone='ok'],
.status-dot[data-tone='ok'] {
  color: var(--color-ok);
}

.telemetry-detail[data-tone='watch'],
.status-dot[data-tone='watch'] {
  color: var(--color-watch);
}

.telemetry-detail[data-tone='alert'],
.status-dot[data-tone='alert'] {
  color: var(--color-alert);
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
  align-items: start;
}

.section-block {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}

.section-head {
  display: grid;
  gap: var(--space-1);
}

.section-head h3 {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.04em;
}

.pipeline-track {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  align-items: stretch;
}

.pipeline-node {
  position: relative;
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4) 0 0;
  border-top: 1px solid var(--color-line-soft);
}

.pipeline-node:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 23px;
  left: calc(100% + 8px);
  width: calc(var(--space-4) - 16px);
  height: 1px;
  background: var(--color-line-strong);
}

.pipeline-track[data-ready='true'] .pipeline-node:not(:last-child)::after {
  background: linear-gradient(90deg, var(--color-line-strong), var(--color-accent), var(--color-line-strong));
  background-size: 200% 100%;
  animation: flow 2.2s linear infinite;
}

.pipeline-node strong,
.threshold-list strong,
.boundary-group h4,
.quality-head strong,
.line-row strong {
  font-size: 16px;
  letter-spacing: -0.03em;
}

.pipeline-node span,
.pipeline-node em {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-style: normal;
}

.pipeline-node em {
  color: var(--color-text-primary);
}

.pipeline-node[data-tone='ok'] em {
  color: var(--color-ok);
}

.pipeline-node[data-tone='watch'] em {
  color: var(--color-watch);
}

.radar-shell {
  height: 280px;
}

.radar-chart {
  height: 100%;
}

.threshold-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-3);
}

.threshold-list article {
  display: grid;
  gap: var(--space-1);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line-soft);
}

.quality-list,
.state-list {
  display: grid;
  gap: var(--space-4);
}

.control-list {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0 0 0 var(--space-4);
  border-left: 2px solid var(--color-line-soft);
  list-style: none;
}

.control-list li {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.state-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: var(--space-6);
}

.quality-item {
  display: grid;
  gap: var(--space-2);
}

.quality-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
}

.quality-bar {
  width: 100%;
  height: 7px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--color-surface-soft);
}

.quality-bar[data-empty='true'] {
  opacity: 0.45;
}

.telemetry-value[data-empty='true'] {
  color: var(--color-text-muted);
}

.quality-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-accent);
}

.boundary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.boundary-group {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  background: rgba(255, 255, 255, 0.015);
  border-radius: var(--radius-sm);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.boundary-group ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: var(--space-2);
}

.line-row {
  display: grid;
  gap: var(--space-1);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line-soft);
}

.state-grid .line-row:nth-child(-n + 2) {
  border-top: none;
  padding-top: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

@keyframes pulse-ring {
  0%, 100% { opacity: 0.52; transform: scale(0.96); }
  50% { opacity: 1; transform: scale(1.04); }
}

@keyframes dash-flow {
  0% { stroke-dashoffset: 0; }
  100% { stroke-dashoffset: -44; }
}

@keyframes flow {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 1200px) {
  .telemetry-strip,
  .pipeline-track,
  .threshold-list,
  .boundary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .page-head,
  .section-grid {
    grid-template-columns: 1fr;
    display: grid;
    align-items: start;
  }

  .page-scene {
    order: -1;
  }

  .telemetry-strip,
  .pipeline-track,
  .threshold-list,
  .boundary-grid,
  .state-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-head h2 {
    font-size: 28px;
  }

  .telemetry-strip,
  .pipeline-track,
  .threshold-list,
  .boundary-grid,
  .state-grid {
    grid-template-columns: 1fr;
  }

  .state-grid .line-row:nth-child(-n + 2) {
    border-top: 1px solid var(--color-line-soft);
    padding-top: var(--space-3);
  }

  .state-grid .line-row:first-child {
    border-top: none;
    padding-top: 0;
  }
}
</style>
