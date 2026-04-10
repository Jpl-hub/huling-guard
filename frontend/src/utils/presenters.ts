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
  near_fall: '高风险失衡',
  fall: '跌倒',
  recovery: '恢复起身',
  prolonged_lying: '长时间卧倒',
  unknown: '未知状态',
  null: '等待判断',
}

const incidentLabels: Record<string, string> = {
  near_fall_warning: '高风险失衡',
  confirmed_fall: '跌倒事件',
  prolonged_lying: '长时间卧倒',
  recovery_detected: '恢复起身',
  recovery: '恢复起身',
  peak_risk_moment: '风险峰值',
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
      { label: '当前是否安全', value: '正在判断', detail: '正在等待稳定结论。', tone: 'neutral' },
      { label: '是否需要马上去看', value: '先继续观察', detail: '当前还没有形成可靠提醒。', tone: 'neutral' },
      { label: '最近发生了什么', value: '还没有关键变化', detail: '热启动完成后会开始记录过程。', tone: 'neutral' },
    ]
  }

  const tone = stateTone(display.predictedState, display.riskScore)
  const currentSafety =
    display.predictedState === 'recovery'
      ? '正在恢复'
      : tone === 'alert'
        ? '存在高风险'
        : tone === 'watch'
          ? '需要警惕'
          : '当前稳定'
  const needGoNow =
    display.predictedState === 'recovery'
      ? '继续值守观察'
      : tone === 'alert'
        ? '立即到场查看'
        : tone === 'watch'
          ? '尽快确认画面'
          : '继续值守观察'
  const recent =
    display.lastIncident != null
      ? `${incidentLabel(display.lastIncident.kind)} · ${formatTimestamp(display.lastIncident.timestamp)}`
      : '暂无正式事件'

  return [
    {
      label: '当前是否安全',
      value: currentSafety,
      detail: `${stateLabel(display.predictedState)}。`,
      tone,
    },
    {
      label: '是否需要马上去看',
      value: needGoNow,
      detail: tone === 'alert' ? '建议马上查看现场。' : tone === 'watch' ? '建议尽快人工确认。' : '当前无需到场。',
      tone,
    },
    {
      label: '最近发生了什么',
      value: recent,
      detail: display.incidentTotal > 0 ? `本段过程累计 ${display.incidentTotal} 条关键事件。` : '本段过程还没有形成正式事件。' ,
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
      badge: '正在热启动',
      title: '正在建立稳定判断',
      action: '保持画面持续输入',
      detail: '系统正在积累连续帧，稍后会给出稳定结论。',
      steps: ['保持摄像头画面稳定。', '等待首个稳定状态生成。'],
    }
  }

  if (display.predictedState === 'fall' || display.predictedState === 'prolonged_lying') {
    return {
      badge: '需要立即处理',
      title: display.predictedState === 'fall' ? '检测到跌倒' : '检测到长时间卧倒',
      action: '立即到场查看',
      detail: '当前已经达到高风险级别，应尽快人工确认现场情况。',
      steps: ['立即查看现场。', '确认人员意识与受伤情况。', '保留本次记录用于后续追溯。'],
    }
  }

  if (display.predictedState === 'near_fall') {
    return {
      badge: '需要尽快确认',
      title: '检测到明显失衡',
      action: '尽快查看画面或到场确认',
      detail: '当前还未形成跌倒事件，但动作过程存在明显风险。',
      steps: ['优先确认人员是否已恢复稳定。', '关注接下来 10 到 20 秒的风险变化。'],
    }
  }

  if (display.predictedState === 'recovery') {
    return {
      badge: '正在恢复',
      title: '人员正在恢复起身',
      action: '持续观察',
      detail: '当前不是高风险告警，但建议继续观察是否稳定恢复。',
      steps: ['观察后续是否回到正常活动。', '如反复波动，建议人工确认。'],
    }
  }

  return {
    badge: '当前稳定',
    title: '当前处于正常活动',
    action: '继续值守',
    detail: '当前没有检测到需要立即到场处理的高风险状态。',
    steps: ['继续观察最近事件与风险变化。', '如需要留档，可保存本次记录。'],
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
  },
): string[] {
  if (mode === 'care') {
    return [
      runtime.archiveEnabled ? '历史记录已启用' : '历史记录未启用',
      runtime.scenePriorLoaded ? '房间先验已加载' : '房间先验未加载',
    ]
  }
  return [
    `窗口 ${runtime.windowSize ?? '-'}`,
    `步长 ${runtime.stride ?? '-'}`,
    `设备 ${runtime.device ?? '-'}`,
    `特征 ${runtime.featureSet ?? '-'}`,
    runtime.scenePriorLoaded ? '房间先验已加载' : '房间先验未加载',
    runtime.archiveEnabled ? '归档已启用' : '归档未启用',
  ]
}
