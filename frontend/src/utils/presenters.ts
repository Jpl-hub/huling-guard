import type {
  DisplayState,
  GuardState,
  Incident,
  QuickAnswer,
  RuntimeStateResponse,
  SessionReport,
  SummaryResponse,
  ViewMode,
} from '../types/runtime'

const stateLabels: Record<string, string> = {
  normal: '正常活动',
  near_fall: '失衡风险',
  fall: '跌倒',
  recovery: '恢复起身',
  prolonged_lying: '长卧风险',
  unknown: '未知状态',
  null: '等待判断',
}

const incidentLabels: Record<string, string> = {
  near_fall_warning: '出现失衡风险',
  confirmed_fall: '检测到跌倒',
  prolonged_lying: '检测到长卧',
  recovery_detected: '检测到起身恢复',
  recovery: '检测到起身恢复',
  peak_risk_moment: '出现风险峰值',
}

const incidentActions: Record<string, string> = {
  near_fall_warning: '先看画面',
  confirmed_fall: '立即到场',
  prolonged_lying: '立即到场',
  recovery_detected: '继续观察',
  recovery: '继续观察',
  peak_risk_moment: '回看确认',
}

export function stateLabel(state: GuardState): string {
  return stateLabels[String(state)] ?? '等待判断'
}

export function incidentLabel(kind: string | null | undefined): string {
  if (!kind) {
    return '暂无事件'
  }
  return incidentLabels[kind] ?? kind
}

export function incidentAction(kind: string | null | undefined): string {
  if (!kind) {
    return '继续值守'
  }
  return incidentActions[kind] ?? '继续值守'
}

export function stateTone(
  state: GuardState,
  riskScore: number,
): 'safe' | 'watch' | 'alert' | 'neutral' {
  if (state === 'fall' || state === 'prolonged_lying') {
    return 'alert'
  }
  if (state === 'recovery') {
    return 'watch'
  }
  if (state === 'near_fall' || riskScore >= 0.55) {
    return 'watch'
  }
  if (state === null || state === 'unknown') {
    return 'neutral'
  }
  return 'safe'
}

export function formatRisk(value: number | null | undefined, digits = 3): string {
  return Number.isFinite(value) ? Number(value).toFixed(digits) : '-'
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (!Number.isFinite(value)) {
    return '-'
  }
  return `${(Number(value) * 100).toFixed(digits)}%`
}

export function formatSeconds(value: number | null | undefined): string {
  if (!Number.isFinite(value)) {
    return '-'
  }
  const seconds = Number(value)
  if (seconds < 60) {
    return `${seconds.toFixed(1)} 秒`
  }
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return `${minutes} 分 ${remain.toFixed(0)} 秒`
}

export function formatTimestamp(value: number | null | undefined): string {
  if (!Number.isFinite(value)) {
    return '-'
  }
  return `${Number(value).toFixed(2)} 秒`
}

export function formatArchiveTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function buildDisplayStateFromRuntime(
  state: RuntimeStateResponse | null,
  summary: SummaryResponse | null,
): DisplayState {
  return {
    predictedState: state?.predicted_state ?? summary?.predicted_state ?? null,
    riskScore: state?.risk_score ?? summary?.risk_score ?? 0,
    confidence: state?.confidence ?? summary?.confidence ?? 0,
    stateProbabilities: state?.state_probs ?? {},
    incidentTotal: summary?.incident_total ?? 0,
    lastIncident: summary?.last_incident ?? null,
    ready: Boolean(state?.ready ?? summary?.ready),
  }
}

export function buildDisplayStateFromReport(report: SessionReport): DisplayState {
  const counts = report.predicted_state_counts ?? {}
  const total = Object.values(counts).reduce((acc, item) => acc + Number(item || 0), 0)
  const probabilities = Object.fromEntries(
    Object.entries(counts).map(([key, value]) => [key, total > 0 ? Number(value) / total : 0]),
  )

  let predictedState = report.dominant_state ?? 'normal'
  if (report.last_incident?.kind === 'confirmed_fall') {
    predictedState = 'fall'
  } else if (report.last_incident?.kind === 'prolonged_lying') {
    predictedState = 'prolonged_lying'
  } else if (report.last_incident?.kind === 'near_fall_warning') {
    predictedState = 'near_fall'
  } else if (report.last_incident?.kind === 'recovery_detected' || report.last_incident?.kind === 'recovery') {
    predictedState = 'recovery'
  } else if (report.peak_risk?.predicted_state) {
    predictedState = report.peak_risk.predicted_state
  }

  return {
    predictedState,
    riskScore: report.incident_total > 0 ? Math.max(report.peak_risk?.risk_score ?? 0, 0.9) : report.peak_risk?.risk_score ?? 0,
    confidence: report.last_incident?.confidence ?? report.peak_risk?.confidence ?? report.mean_confidence ?? 0,
    stateProbabilities: probabilities,
    incidentTotal: report.incident_total ?? 0,
    lastIncident: report.last_incident ?? null,
    ready: report.ready_frames > 0,
  }
}

export function buildReportIncidents(report: SessionReport): Incident[] {
  if (report.recent_incidents?.length) {
    return report.recent_incidents
  }
  if (report.peak_risk) {
    return [
      {
        kind: 'peak_risk_moment',
        timestamp: report.peak_risk.timestamp,
        confidence: report.peak_risk.confidence,
        payload: {
          predicted_state: report.peak_risk.predicted_state,
          risk_score: report.peak_risk.risk_score,
        },
      },
    ]
  }
  return []
}

export function buildQuickAnswers(
  display: DisplayState,
): QuickAnswer[] {
  if (!display.ready) {
    return [
      { label: '当前是否安全', value: '正在判断', detail: '等待连续画面稳定', tone: 'neutral' },
      { label: '是否需要过去', value: '先持续观察', detail: '还没有形成正式提醒', tone: 'neutral' },
      { label: '最近发生了什么', value: '暂无关键变化', detail: '系统仍在建立首段状态流', tone: 'neutral' },
    ]
  }

  const tone = stateTone(display.predictedState, display.riskScore)
  const currentSafety =
    display.predictedState === 'recovery'
      ? '正在恢复'
      : tone === 'alert'
        ? '存在高风险'
        : tone === 'watch'
          ? '需要留意'
          : '当前稳定'
  const needGoNow =
    display.predictedState === 'recovery'
      ? '继续看画面'
      : tone === 'alert'
        ? '现在就去看'
        : tone === 'watch'
          ? '尽快确认'
          : '暂不到场'
  const recent =
    display.lastIncident != null
      ? `${incidentLabel(display.lastIncident.kind)} · ${formatTimestamp(display.lastIncident.timestamp)}`
      : '没有正式提醒'

  return [
    {
      label: '当前是否安全',
      value: currentSafety,
      detail: stateLabel(display.predictedState),
      tone,
    },
    {
      label: '是否需要过去',
      value: needGoNow,
      detail: tone === 'alert' ? '先处理现场' : tone === 'watch' ? '先确认画面' : '继续值守即可',
      tone,
    },
    {
      label: '最近发生了什么',
      value: recent,
      detail: display.incidentTotal > 0 ? `累计 ${display.incidentTotal} 次提醒` : '当前无提醒',
      tone: display.incidentTotal > 0 ? 'watch' : 'safe',
    },
  ]
}

export function buildVerdict(display: DisplayState): {
  badge: string
  title: string
  action: string
  detail: string
  steps: string[]
} {
  if (!display.ready) {
    return {
      badge: '正在建立判断',
      title: '等待首段稳定状态',
      action: '保持当前画面',
      detail: '系统正在收集足够的连续画面。',
      steps: ['保持画面连续输入', '等待首个稳定结论'],
    }
  }

  if (display.predictedState === 'fall' || display.predictedState === 'prolonged_lying') {
    return {
      badge: '立即处理',
      title: display.predictedState === 'fall' ? '已检测到跌倒' : '已检测到长卧风险',
      action: '立即到场查看',
      detail: '这一段画面已经达到高风险级别。',
      steps: ['先到场确认人员状态', '完成处理后再归档本段过程'],
    }
  }

  if (display.predictedState === 'near_fall') {
    return {
      badge: '尽快确认',
      title: '画面中出现明显失衡',
      action: '先看画面，再决定是否过去',
      detail: '当前还不是跌倒结论，但风险已经抬高。',
      steps: ['先确认是否已经恢复稳定', '若继续恶化则立即处理'],
    }
  }

  if (display.predictedState === 'recovery') {
    return {
      badge: '正在恢复',
      title: '人物正在恢复起身',
      action: '继续观察',
      detail: '当前不属于高风险告警，但仍要继续值守。',
      steps: ['确认是否回到正常活动', '若再次波动则重新判断'],
    }
  }

  return {
    badge: '当前稳定',
    title: '当前为正常活动',
    action: '继续值守',
    detail: '这段画面没有出现需要立刻处理的风险。',
    steps: ['保持当前监看', '需要时再归档本段过程'],
  }
}

export function runtimeChips(
  mode: ViewMode,
  runtime: {
    windowSize?: number
    stride?: number
    device?: string
    featureSet?: string
    archiveEnabled?: boolean
    scenePriorLoaded?: boolean
    poseQualityScore?: number
    meanKeypointConfidence?: number
    visibleJointRatio?: number
  },
): string[] {
  if (mode === 'care') {
    return [
      runtime.archiveEnabled ? '历史归档已开启' : '历史归档未开启',
      runtime.scenePriorLoaded ? '房间先验已加载' : '房间先验未加载',
    ]
  }
  return [
    `窗口 ${runtime.windowSize ?? '-'}`,
    `步长 ${runtime.stride ?? '-'}`,
    `设备 ${runtime.device ?? '-'}`,
    `特征 ${runtime.featureSet ?? '-'}`,
    `骨架质量 ${formatRisk(runtime.poseQualityScore)}`,
    `关键点均值 ${formatPercent(runtime.meanKeypointConfidence)}`,
    `可见关节 ${formatPercent(runtime.visibleJointRatio)}`,
    runtime.scenePriorLoaded ? '房间先验已加载' : '房间先验未加载',
    runtime.archiveEnabled ? '历史归档已开启' : '历史归档未开启',
  ]
}
