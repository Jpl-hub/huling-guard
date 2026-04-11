import type {
  DisplayState,
  GuardState,
  Incident,
  QuickAnswer,
  RuntimeStateResponse,
  SessionReport,
  SummaryResponse,
  TimelineItem,
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

export function archiveDisplayName(
  sessionName: string | null | undefined,
  archivedAt: string | null | undefined,
  fallback: string | null | undefined = null,
): string {
  const normalized = String(sessionName ?? '').trim()
  if (normalized && !/^runtime(_|$)/i.test(normalized) && !/^session[_-]/i.test(normalized)) {
    return normalized
  }
  if (fallback) {
    return fallback
  }
  const timeLabel = formatArchiveTime(archivedAt)
  return timeLabel === '-' ? '回看记录' : `回看记录 · ${timeLabel}`
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

function dedupeIncidents(incidents: Incident[]): Incident[] {
  const seen = new Set<string>()
  const unique: Incident[] = []
  for (const incident of incidents) {
    const key = `${incident.kind}-${Number(incident.timestamp ?? 0).toFixed(3)}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    unique.push(incident)
  }
  return unique
}

function buildDerivedTimelineIncidents(items: ReadonlyArray<TimelineItem>): Incident[] {
  const derived: Incident[] = []
  let previousState: GuardState = null
  for (const item of items) {
    if (!item.ready || !item.predicted_state || item.predicted_state === 'normal') {
      previousState = item.predicted_state ?? previousState
      continue
    }
    if (item.predicted_state === previousState) {
      continue
    }
    const kind =
      item.predicted_state === 'near_fall'
        ? 'near_fall_warning'
        : item.predicted_state === 'fall'
          ? 'confirmed_fall'
          : item.predicted_state === 'prolonged_lying'
            ? 'prolonged_lying'
            : item.predicted_state === 'recovery'
              ? 'recovery_detected'
              : null
    if (kind) {
      derived.push({
        kind,
        timestamp: Number(item.timestamp ?? 0),
        confidence: Number(item.confidence ?? 0),
        payload: {
          predicted_state: item.predicted_state,
          risk_score: Number(item.risk_score ?? 0),
        },
      })
    }
    previousState = item.predicted_state
  }
  return derived
}

export function buildTimelineIncidents(items: ReadonlyArray<TimelineItem>, limit = 12): Incident[] {
  const explicit = items.flatMap((item) =>
    (item.incidents ?? []).map((incident) => ({
      kind: String(incident.kind ?? 'unknown'),
      timestamp: Number(incident.timestamp ?? item.timestamp ?? 0),
      confidence: Number(incident.confidence ?? item.confidence ?? 0),
      payload: (incident.payload ?? {
        predicted_state: item.predicted_state,
        risk_score: Number(item.risk_score ?? 0),
      }) as Record<string, unknown>,
    })),
  )
  return dedupeIncidents([...explicit, ...buildDerivedTimelineIncidents(items)])
    .sort((left, right) => Number(right.timestamp) - Number(left.timestamp))
    .slice(0, limit)
}

function buildStateSegmentsFromTimeline(items: ReadonlyArray<TimelineItem>) {
  const readyItems = items.filter((item) => item.ready && item.predicted_state)
  const segments: SessionReport['state_segments'] = []
  let current: SessionReport['state_segments'][number] | null = null

  for (const item of readyItems) {
    if (current == null || current.state !== item.predicted_state) {
      if (current != null) {
        current.duration_seconds = Math.max(0, current.end_timestamp - current.start_timestamp)
        segments.push(current)
      }
      current = {
        state: item.predicted_state,
        start_timestamp: Number(item.timestamp ?? 0),
        end_timestamp: Number(item.timestamp ?? 0),
        frame_count: 1,
        max_risk_score: Number(item.risk_score ?? 0),
        max_confidence: Number(item.confidence ?? 0),
        duration_seconds: 0,
      }
      continue
    }

    current.end_timestamp = Number(item.timestamp ?? current.end_timestamp)
    current.frame_count += 1
    current.max_risk_score = Math.max(current.max_risk_score, Number(item.risk_score ?? 0))
    current.max_confidence = Math.max(current.max_confidence, Number(item.confidence ?? 0))
  }

  if (current != null) {
    current.duration_seconds = Math.max(0, current.end_timestamp - current.start_timestamp)
    segments.push(current)
  }

  return segments
}

export function buildDisplayStateFromTimeline(
  items: ReadonlyArray<TimelineItem>,
  playbackStarted: boolean,
): DisplayState {
  if (!playbackStarted || !items.length) {
    return {
      predictedState: null,
      riskScore: 0,
      confidence: 0,
      stateProbabilities: {},
      incidentTotal: 0,
      lastIncident: null,
      ready: false,
    }
  }

  const latest = [...items].reverse().find((item) => item.predicted_state) ?? items[items.length - 1]
  const incidents = buildTimelineIncidents(items)
  const readyItems = items.filter((item) => item.ready)
  const counts = readyItems.reduce<Record<string, number>>((acc, item) => {
    if (item.predicted_state) {
      acc[item.predicted_state] = (acc[item.predicted_state] ?? 0) + 1
    }
    return acc
  }, {})
  const total = Object.values(counts).reduce((sum, value) => sum + Number(value), 0)

  return {
    predictedState: latest.predicted_state ?? null,
    riskScore: Number(latest.risk_score ?? 0),
    confidence: Number(latest.confidence ?? 0),
    stateProbabilities:
      latest.state_probs && Object.keys(latest.state_probs).length
        ? latest.state_probs
        : Object.fromEntries(Object.entries(counts).map(([key, value]) => [key, total > 0 ? value / total : 0])),
    incidentTotal: incidents.length,
    lastIncident: incidents[0] ?? null,
    ready: readyItems.length > 0,
  }
}

export function buildSessionReportFromTimeline(
  baseReport: SessionReport,
  items: ReadonlyArray<TimelineItem>,
  playbackStarted: boolean,
): SessionReport | null {
  if (!playbackStarted || !items.length) {
    return null
  }

  const readyItems = items.filter((item) => item.ready)
  const incidents = buildTimelineIncidents(items, 64).sort((left, right) => Number(left.timestamp) - Number(right.timestamp))
  const segments = buildStateSegmentsFromTimeline(items)
  const counts = readyItems.reduce<Record<string, number>>((acc, item) => {
    if (item.predicted_state) {
      acc[item.predicted_state] = (acc[item.predicted_state] ?? 0) + 1
    }
    return acc
  }, {})
  const incidentCounts = incidents.reduce<Record<string, number>>((acc, incident) => {
    acc[incident.kind] = (acc[incident.kind] ?? 0) + 1
    return acc
  }, {})
  const dominantState =
    (Object.entries(counts).sort((left, right) => Number(right[1]) - Number(left[1]))[0]?.[0] as GuardState | undefined) ?? null
  const peak = readyItems.reduce<TimelineItem | null>((best, item) => {
    if (best == null || Number(item.risk_score) > Number(best.risk_score)) {
      return item
    }
    return best
  }, null)
  const endTimestamp = Number(items[items.length - 1]?.timestamp ?? 0)

  return {
    ...baseReport,
    total_frames: items.length,
    ready_frames: readyItems.length,
    warmup_frames: Math.max(0, items.length - readyItems.length),
    ready_ratio: items.length > 0 ? readyItems.length / items.length : 0,
    start_timestamp: 0,
    end_timestamp: endTimestamp,
    duration_seconds: Math.max(0, endTimestamp),
    peak_risk: peak
      ? {
          timestamp: Number(peak.timestamp ?? 0),
          predicted_state: peak.predicted_state ?? null,
          risk_score: Number(peak.risk_score ?? 0),
          confidence: Number(peak.confidence ?? 0),
        }
      : null,
    mean_risk_score:
      readyItems.length > 0
        ? readyItems.reduce((sum, item) => sum + Number(item.risk_score ?? 0), 0) / readyItems.length
        : 0,
    mean_confidence:
      readyItems.length > 0
        ? readyItems.reduce((sum, item) => sum + Number(item.confidence ?? 0), 0) / readyItems.length
        : 0,
    dominant_state: dominantState,
    predicted_state_counts: counts,
    incident_total: incidents.length,
    incident_counts: incidentCounts,
    first_incident: incidents[0] ?? null,
    last_incident: incidents[incidents.length - 1] ?? null,
    recent_incidents: incidents.slice(-5),
    top_risk_moments: [...readyItems]
      .sort((left, right) => Number(right.risk_score) - Number(left.risk_score))
      .slice(0, 5)
      .map((item) => ({
        timestamp: Number(item.timestamp ?? 0),
        predicted_state: item.predicted_state ?? null,
        risk_score: Number(item.risk_score ?? 0),
        confidence: Number(item.confidence ?? 0),
      })),
    state_segments: segments,
    longest_segments: [...segments]
      .sort((left, right) => Number(right.duration_seconds) - Number(left.duration_seconds))
      .slice(0, 5),
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
      { label: '当前是否安全', value: '等待连续结论', detail: '系统正在建立第一段连续判断', tone: 'neutral' },
      { label: '是否需要过去', value: '先持续观察', detail: '暂时不用处理', tone: 'neutral' },
      { label: '最近发生了什么', value: '分析已经开始', detail: '等时序窗口稳定后给正式结论', tone: 'neutral' },
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
      ? '继续观察'
      : tone === 'alert'
        ? '现在就去看'
        : tone === 'watch'
          ? '尽快确认'
          : '暂时不用过去'
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
      detail: display.incidentTotal > 0 ? `本段共 ${display.incidentTotal} 次提醒` : '画面保持稳定',
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
      badge: '正在建立连续判断',
      title: '先保持画面连续',
      action: '暂不处理',
      detail: '系统已进入分析，正在形成第一段连续状态。',
      steps: ['保持画面连续输入', '等结论稳定后再处理'],
    }
  }

  if (display.predictedState === 'fall' || display.predictedState === 'prolonged_lying') {
    return {
      badge: '立即处理',
      title: display.predictedState === 'fall' ? '建议马上到场查看' : '建议马上查看长卧情况',
      action: '现在过去',
      detail: '这段画面已经出现需要处理的高风险过程。',
      steps: ['先到现场确认人员状态', '处理完成后保存这段画面'],
    }
  }

  if (display.predictedState === 'near_fall') {
    return {
      badge: '尽快确认',
      title: '先确认是否已经失衡',
      action: '先看画面，再决定是否过去',
      detail: '当前风险明显抬高，但还不是最终跌倒结论。',
      steps: ['先确认人员是否已经站稳', '如果动作继续恶化就立即到场'],
    }
  }

  if (display.predictedState === 'recovery') {
    return {
      badge: '继续观察',
      title: '当前像是在恢复起身',
      action: '继续看 5 到 10 秒',
      detail: '目前不属于高风险告警，但还要继续看后续动作。',
      steps: ['确认人员是否回到正常活动', '如果再次失衡就重新判断'],
    }
  }

  return {
    badge: '当前稳定',
    title: '当前无须处理',
    action: '继续值守',
    detail: '这段画面没有出现需要立刻处理的风险。',
    steps: ['保持当前监看', '需要复盘时再保存这段画面'],
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
