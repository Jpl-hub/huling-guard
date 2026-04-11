export type GuardState =
  | 'normal'
  | 'near_fall'
  | 'fall'
  | 'recovery'
  | 'prolonged_lying'
  | 'unknown'
  | null

export type ViewMode = 'care' | 'xray'

export interface HealthResponse {
  status: string
  window_size: number
  inference_stride: number
}

export interface Thresholds {
  near_fall?: number
  fall?: number
  recovery?: number
  prolonged_lying?: number
  prolonged_lying_seconds?: number
  warning_cooldown_seconds?: number
}

export interface MetaResponse {
  title: string
  window_size: number
  inference_stride: number
  device: string
  kinematic_feature_set: string
  scene_prior_loaded: boolean
  archive_enabled: boolean
  archive_backend: string | null
  thresholds: Thresholds
}

export interface PoseQualityMetrics {
  pose_quality_score: number
  mean_keypoint_confidence: number
  visible_joint_ratio: number
}

export interface RuntimeStateResponse {
  timestamp: number
  ready: boolean
  observed_frames: number
  window_size: number
  window_span_seconds: number
  data_quality: PoseQualityMetrics
  predicted_state: GuardState
  state_probs: Record<string, number>
  risk_score: number
  confidence: number
  incidents: Incident[]
}

export interface SummaryResponse {
  ready: boolean
  observed_frames: number
  predicted_state: GuardState
  risk_score: number
  confidence: number
  incident_total: number
  incident_counts: Record<string, number>
  last_incident: Incident | null
  timeline_points: number
  data_quality: PoseQualityMetrics
}

export interface TimelineItem {
  timestamp: number
  ready?: boolean
  predicted_state: GuardState
  state_probs?: Record<string, number>
  risk_score: number
  confidence: number
  incidents?: Incident[]
}

export interface TimelineResponse {
  count: number
  items: TimelineItem[]
}

export interface Incident {
  kind: string
  timestamp: number
  confidence: number
  payload?: Record<string, unknown>
}

export interface TopRiskMoment {
  timestamp: number
  predicted_state: GuardState
  risk_score: number
  confidence: number
}

export interface StateSegment {
  state: GuardState
  start_timestamp: number
  end_timestamp: number
  frame_count: number
  max_risk_score: number
  max_confidence: number
  duration_seconds: number
}

export interface SessionReport {
  session_id?: string
  archived_at?: string
  session_name: string
  source_path: string
  total_frames: number
  ready_frames: number
  warmup_frames: number
  ready_ratio: number
  start_timestamp: number
  end_timestamp: number
  duration_seconds: number
  peak_risk: TopRiskMoment | null
  mean_risk_score: number
  mean_confidence: number
  dominant_state: GuardState
  predicted_state_counts: Record<string, number>
  incident_total: number
  incident_counts: Record<string, number>
  first_incident: Incident | null
  last_incident: Incident | null
  recent_incidents: Incident[]
  top_risk_moments: TopRiskMoment[]
  state_segments: StateSegment[]
  longest_segments: StateSegment[]
}

export interface DemoVideoItem {
  name: string
  filename: string
  size_bytes: number
  url: string
  poster_url?: string | null
  has_session_report: boolean
  source_kind?: 'demo' | 'upload' | string
  processing_status?: 'ready' | 'processing' | 'failed' | string
  original_name?: string | null
  error_message?: string | null
  processed_frames?: number | null
  total_frames?: number | null
}

export interface DemoVideosResponse {
  enabled: boolean
  root: string | null
  count: number
  items: DemoVideoItem[]
}

export interface DemoSessionResponse {
  name: string
  session_report: SessionReport
  timeline: TimelineResponse
}

export interface UploadVideoResponse {
  status: string
  item: DemoVideoItem
  metadata: Record<string, unknown>
}

export interface LiveSourceResponse {
  available: boolean
  source: string | null
  source_label: string | null
  timestamp: number | null
  frame_width: number | null
  frame_height: number | null
  annotated: boolean
  updated_at: number | null
}

export interface LiveIngestStatusResponse {
  status: 'idle' | 'starting' | 'running' | 'stopping' | 'stopped' | 'completed' | 'failed' | string
  active: boolean
  source: string | null
  source_label: string | null
  rtmo_device: string | null
  frame_stride: number | null
  preview_stride: number | null
  loop: boolean
  processed_frames: number
  started_at: number | null
  finished_at: number | null
  error_message: string | null
}

export interface DetectableState {
  code: string
  label: string
}

export interface SystemModule {
  name: string
  summary: string
}

export interface RuntimeProfile {
  device: string
  window_size: number
  inference_stride: number
  kinematic_feature_set: string
  scene_prior_loaded: boolean
  archive_enabled: boolean
}

export interface SystemProfileResponse {
  product_name: string
  product_tagline: string
  target_users: string[]
  operational_goals: string[]
  detectable_states: DetectableState[]
  system_modules: SystemModule[]
  runtime_profile: RuntimeProfile
  quality_controls: string[]
  thresholds: Thresholds
}

export interface ArchiveRecord {
  session_id: string
  session_name: string | null
  archived_at: string
  dominant_state: GuardState
  duration_seconds: number
  incident_total: number
  peak_risk_score: number
  json_path?: string
  markdown_path?: string
}

export interface ArchiveListResponse {
  count: number
  items: ArchiveRecord[]
}

export interface ArchiveSummaryResponse {
  archive_total: number
  total_incidents: number
  mean_duration_seconds: number
  max_peak_risk_score: number
  sessions_with_incidents: number
  dominant_state_counts: Record<string, number>
  latest_archive: {
    session_id: string
    session_name: string | null
    archived_at: string
    dominant_state: GuardState
  } | null
}

export interface DisplayState {
  predictedState: GuardState
  riskScore: number
  confidence: number
  stateProbabilities: Record<string, number>
  incidentTotal: number
  lastIncident: Incident | null
  ready: boolean
}

export interface QuickAnswer {
  label: string
  value: string
  detail: string
  tone: 'safe' | 'watch' | 'alert' | 'neutral'
}
