<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'

import type { GuardState, TimelineItem } from '../types/runtime'
import { formatRisk, formatTimestamp, stateLabel, stateTone } from '../utils/presenters'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const props = defineProps<{
  items: ReadonlyArray<TimelineItem>
}>()

const peak = computed(() =>
  props.items.reduce<TimelineItem | null>((best, item) => {
    if (best == null || item.risk_score > best.risk_score) {
      return item
    }
    return best
  }, null),
)

const option = computed(() => ({
  animation: false,
  grid: { left: 18, right: 18, top: 26, bottom: 26, containLabel: true },
  tooltip: {
    trigger: 'axis',
    borderWidth: 0,
    backgroundColor: 'rgba(5, 14, 24, 0.92)',
    textStyle: { color: '#f5fbff' },
    formatter: (params: Array<{ data: [number, number, string | null] }>) => {
      const [item] = params
      const state = item?.data?.[2]
      return [
        `时间 ${formatTimestamp(item?.data?.[0] ?? 0)}`,
        `风险 ${formatRisk(item?.data?.[1] ?? 0)}`,
        `状态 ${stateLabel((state ?? null) as GuardState)}`,
      ].join('<br>')
    },
  },
  xAxis: {
    type: 'category',
    data: props.items.map((item) => formatTimestamp(item.timestamp)),
    axisLine: { lineStyle: { color: 'rgba(150, 176, 203, 0.2)' } },
    axisLabel: { color: 'rgba(185, 205, 226, 0.58)', fontSize: 11, hideOverlap: true },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 1,
    splitLine: { lineStyle: { color: 'rgba(150, 176, 203, 0.1)' } },
    axisLabel: { color: 'rgba(185, 205, 226, 0.58)', fontSize: 11 },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: {
        width: 3,
        color: '#40d6ff',
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64, 214, 255, 0.35)' },
            { offset: 1, color: 'rgba(64, 214, 255, 0.02)' },
          ],
        },
      },
      data: props.items.map((item) => [item.timestamp, item.risk_score, item.predicted_state]),
    },
  ],
}))
</script>

<template>
  <section class="timeline-panel">
    <header class="head">
      <div>
        <h2>风险时间线</h2>
        <p>
          <template v-if="peak">
            最高风险出现在 {{ formatTimestamp(peak.timestamp) }}，状态 {{ stateLabel(peak.predicted_state) }}。
          </template>
          <template v-else>
            当前还没有足够的时间线数据。
          </template>
        </p>
      </div>
      <span v-if="peak" class="peak-chip" :data-tone="stateTone(peak.predicted_state, peak.risk_score)">
        峰值 {{ formatRisk(peak.risk_score) }}
      </span>
    </header>

    <div v-if="items.length" class="chart-shell">
      <VChart :option="option" autoresize class="chart" />
    </div>
    <div v-else class="empty">
      暂无稳定时间线。系统完成热启动后，这里会显示风险变化轨迹。
    </div>
  </section>
</template>

<style scoped>
.timeline-panel {
  display: grid;
  gap: 18px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.head p {
  margin: 0;
  color: rgba(199, 214, 231, 0.72);
  font-size: 13px;
  line-height: 1.55;
}

.peak-chip {
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.04);
}

.peak-chip[data-tone='alert'] {
  color: #ffd2cf;
  background: rgba(255, 94, 98, 0.16);
}

.peak-chip[data-tone='watch'] {
  color: #ffe4b8;
  background: rgba(255, 179, 71, 0.16);
}

.peak-chip[data-tone='safe'] {
  color: #b8ffdf;
  background: rgba(54, 211, 153, 0.15);
}

.chart-shell {
  height: 280px;
  border-radius: 24px;
  border: 1px solid rgba(120, 146, 176, 0.14);
  background: rgba(7, 17, 29, 0.72);
}

.chart {
  height: 100%;
}

.empty {
  display: grid;
  place-items: center;
  min-height: 220px;
  border-radius: 24px;
  border: 1px dashed rgba(120, 146, 176, 0.18);
  background: rgba(255, 255, 255, 0.02);
  color: rgba(199, 214, 231, 0.62);
  text-align: center;
}
</style>
