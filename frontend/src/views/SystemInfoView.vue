<script setup lang="ts">
import { computed, ref } from 'vue'
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
const sceneTiltX = ref(0)
const sceneTiltY = ref(0)
const sceneStyle = computed<Record<string, string>>(() => ({
  '--scene-tilt-x': `${sceneTiltX.value.toFixed(2)}deg`,
  '--scene-tilt-y': `${sceneTiltY.value.toFixed(2)}deg`,
}))

function handleScenePointerMove(event: PointerEvent): void {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  if (!rect.width || !rect.height) {
    return
  }
  const offsetX = ((event.clientX - rect.left) / rect.width - 0.5) * 2
  const offsetY = ((event.clientY - rect.top) / rect.height - 0.5) * 2
  sceneTiltX.value = -offsetY * 4
  sceneTiltY.value = offsetX * 5
}

function resetSceneTilt(): void {
  sceneTiltX.value = 0
  sceneTiltY.value = 0
}

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
  animation: true,
  animationDuration: 900,
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
    axisName: { color: 'rgba(214, 225, 237, 0.78)', fontSize: 12 },
    splitLine: { lineStyle: { color: ['rgba(121, 212, 231, 0.08)', 'rgba(121, 212, 231, 0.14)'] } },
    splitArea: { areaStyle: { color: ['rgba(121, 212, 231, 0.00)', 'rgba(121, 212, 231, 0.025)'] } },
    axisLine: { lineStyle: { color: 'rgba(121, 212, 231, 0.06)' } },
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
      lineStyle: { width: 2, color: '#79d4e7', shadowBlur: 12, shadowColor: 'rgba(121, 212, 231, 0.42)' },
      itemStyle: { color: '#79d4e7', borderColor: 'rgba(245, 251, 255, 0.86)', borderWidth: 1 },
      areaStyle: {
        color: {
          type: 'radial',
          x: 0.5,
          y: 0.5,
          r: 0.72,
          colorStops: [
            { offset: 0, color: 'rgba(121, 212, 231, 0.30)' },
            { offset: 0.7, color: 'rgba(121, 212, 231, 0.12)' },
            { offset: 1, color: 'rgba(121, 212, 231, 0.02)' },
          ],
        },
      },
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
        <ul class="page-points">
          <li>RTMO 负责骨架提取与输入质量门控。</li>
          <li>时序网络负责连续动作状态判断。</li>
          <li>事件引擎负责提醒升级、归档与复核。</li>
        </ul>
      </div>

      <div class="page-scene">
        <div
          class="scene-shell"
          :data-ready="runtimeReady"
          :style="sceneStyle"
          role="img"
          aria-label="固定机位场景下的三层运行引擎示意"
          @pointermove="handleScenePointerMove"
          @pointerleave="resetSceneTilt"
        >
          <div class="scene-glow" aria-hidden="true" />
          <div class="scene-stack" aria-hidden="true">
            <div class="scene-plane layer-base">
              <div class="room-grid">
                <span class="zone zone-bed">床面区</span>
                <span class="zone zone-floor">地面区</span>
                <span class="zone zone-edge">边界区</span>
              </div>
            </div>

            <div class="scene-plane layer-pose">
              <span class="skeleton-line spine" />
              <span class="skeleton-line shoulder" />
              <span class="skeleton-line hip" />
              <span class="skeleton-line left-leg" />
              <span class="skeleton-line right-leg" />
              <span class="joint head" />
              <span class="joint chest" />
              <span class="joint pelvis" />
              <span class="joint left-knee" />
              <span class="joint right-knee" />
            </div>

            <div class="scene-plane layer-events">
              <span class="scanner-line" />
              <span class="event-lane lane-a" />
              <span class="event-lane lane-b" />
              <span class="event-lane lane-c" />
              <span class="event-node node-a" />
              <span class="event-node node-b" />
            </div>
          </div>

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
  --scene-tilt-x: 0deg;
  --scene-tilt-y: 0deg;
  position: relative;
  width: 100%;
  min-height: 360px;
  overflow: hidden;
  border-radius: var(--radius-md);
  background:
    radial-gradient(circle at 50% 54%, rgba(121, 212, 231, 0.13), transparent 34%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.012));
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.055),
    0 26px 80px rgba(0, 0, 0, 0.24);
  perspective: 920px;
  transform-style: preserve-3d;
}

.scene-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
  background-size: 34px 34px;
  opacity: 0.15;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.9), transparent 86%);
}

.scene-glow {
  position: absolute;
  inset: 16% 12% 12%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(121, 212, 231, 0.16), transparent 66%);
  filter: blur(18px);
  opacity: 0.75;
}

.scene-stack {
  position: absolute;
  inset: 40px 54px 70px;
  transform-style: preserve-3d;
  transform: rotateX(calc(58deg + var(--scene-tilt-x))) rotateZ(calc(-38deg + var(--scene-tilt-y))) translateY(8px);
  transition: transform 180ms ease-out;
}

.scene-plane {
  position: absolute;
  inset: 0;
  border-radius: 18px;
  transform-style: preserve-3d;
}

.layer-base {
  transform: translateZ(0);
  background:
    linear-gradient(90deg, rgba(121, 212, 231, 0.10), transparent 1px),
    linear-gradient(rgba(121, 212, 231, 0.08), transparent 1px),
    rgba(4, 13, 22, 0.78);
  background-size: 42px 42px;
  box-shadow:
    inset 0 0 0 1px rgba(121, 212, 231, 0.16),
    0 24px 46px rgba(0, 0, 0, 0.22);
}

.room-grid {
  position: absolute;
  inset: 16px;
  border: 1px solid rgba(121, 212, 231, 0.20);
  border-radius: 14px;
}

.zone {
  position: absolute;
  display: grid;
  place-items: center;
  min-width: 76px;
  min-height: 44px;
  border-radius: 12px;
  color: rgba(245, 251, 255, 0.86);
  font-size: 12px;
  letter-spacing: 0.08em;
  background: rgba(121, 212, 231, 0.055);
  box-shadow: inset 0 0 0 1px rgba(121, 212, 231, 0.18);
  transform: translateZ(8px);
}

.zone-bed {
  left: 10%;
  bottom: 12%;
}

.zone-floor {
  left: 48%;
  bottom: 20%;
  background: rgba(255, 172, 92, 0.07);
  box-shadow: inset 0 0 0 1px rgba(255, 172, 92, 0.2);
}

.zone-edge {
  top: 14%;
  right: 12%;
}

.layer-pose {
  inset: 7% 13% 16% 24%;
  transform: translateZ(54px);
  border: 1px solid rgba(126, 242, 189, 0.14);
  box-shadow: 0 0 28px rgba(126, 242, 189, 0.05);
}

.joint,
.event-node {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: var(--color-ok);
  box-shadow: 0 0 16px rgba(126, 242, 189, 0.52);
}

.skeleton-line {
  position: absolute;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(126, 242, 189, 0.18), rgba(126, 242, 189, 0.86));
  box-shadow: 0 0 10px rgba(126, 242, 189, 0.34);
  transform-origin: left center;
}

.head { left: 48%; top: 18%; }
.chest { left: 50%; top: 36%; }
.pelvis { left: 52%; top: 55%; }
.left-knee { left: 38%; top: 72%; }
.right-knee { left: 66%; top: 70%; }
.spine { left: 50%; top: 23%; width: 78px; transform: rotate(84deg); }
.shoulder { left: 39%; top: 38%; width: 112px; transform: rotate(-2deg); }
.hip { left: 45%; top: 57%; width: 92px; transform: rotate(4deg); }
.left-leg { left: 42%; top: 58%; width: 90px; transform: rotate(115deg); }
.right-leg { left: 58%; top: 58%; width: 86px; transform: rotate(66deg); }

.layer-events {
  overflow: hidden;
  transform: translateZ(108px);
  pointer-events: none;
}

.scanner-line {
  position: absolute;
  inset: -16% auto -16% 12%;
  width: 58px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(245, 251, 255, 0.46), rgba(121, 212, 231, 0.78), transparent);
  filter: blur(8px);
  mix-blend-mode: screen;
  opacity: 0.74;
  transform: skewX(-18deg);
  animation: scanner-pass 3.4s ease-in-out infinite;
}

.scene-shell[data-ready='false'] .scanner-line {
  animation: none;
  opacity: 0.12;
}

.event-lane {
  position: absolute;
  left: 8%;
  right: 8%;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(121, 212, 231, 0.95), transparent);
  background-size: 240% 100%;
  box-shadow: 0 0 18px rgba(121, 212, 231, 0.42);
  animation: lane-scan 2.8s linear infinite;
}

.scene-shell[data-ready='false'] .event-lane {
  animation: none;
  opacity: 0.22;
}

.lane-a { top: 22%; }
.lane-b { top: 52%; animation-delay: -0.9s; }
.lane-c { top: 76%; animation-delay: -1.8s; }
.node-a { left: 28%; top: 48%; background: var(--color-watch); box-shadow: 0 0 16px rgba(242, 202, 123, 0.45); }
.node-b { right: 21%; top: 21%; background: var(--color-accent); }

.scene-tag {
  position: absolute;
  z-index: 2;
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
  font-family: var(--font-mono);
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
  display: flex;
  align-items: center;
  min-height: 28px;
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

@keyframes lane-scan {
  0% { background-position: 220% 0; opacity: 0.28; }
  42% { opacity: 0.94; }
  100% { background-position: -220% 0; opacity: 0.28; }
}

@keyframes scanner-pass {
  0%, 20% { transform: translateX(-80px) skewX(-18deg); opacity: 0; }
  42% { opacity: 0.78; }
  78%, 100% { transform: translateX(520px) skewX(-18deg); opacity: 0; }
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

  .scene-shell {
    min-height: 320px;
  }

  .scene-stack {
    inset: 62px 36px 86px;
    transform: rotateX(calc(58deg + var(--scene-tilt-x))) rotateZ(calc(-38deg + var(--scene-tilt-y))) translateY(8px) scale(0.86);
  }

  .tag-input {
    max-width: 180px;
  }

  .tag-pose {
    left: 18px;
    bottom: 18px;
    min-width: 0;
    max-width: 180px;
    transform: none;
  }

  .tag-engine {
    top: auto;
    right: 18px;
    bottom: 18px;
    max-width: 180px;
  }

  .state-grid .line-row:first-child {
    border-top: none;
    padding-top: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .scene-stack,
  .event-lane,
  .scanner-line,
  .pipeline-track[data-ready='true'] .pipeline-node:not(:last-child)::after,
  .status-dot {
    animation: none;
    transition: none;
  }
}
</style>
