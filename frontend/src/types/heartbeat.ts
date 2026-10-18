export interface QuietHours {
  start: string
  end: string
}

export interface HeartbeatConfig {
  character_id: number
  enabled: boolean
  interval_min: number
  types: string[] // monologue | proactive
  quiet_hours: QuietHours
  daily_limit: number
  jitter_ratio: number
  show_monologue: boolean
  last_run_at: string | null
  next_run_at: string | null
  today_count: number
  quiet_now: boolean
  updated_at: string
}

export interface HeartbeatConfigUpdate {
  enabled?: boolean
  interval_min?: number
  types?: string[]
  quiet_hours?: QuietHours
  daily_limit?: number
  jitter_ratio?: number
  show_monologue?: boolean
}

export interface HeartbeatRun {
  id: number
  character_id: number
  conversation_id: number | null
  type: string // monologue | proactive
  status: string // running | done | failed
  output: string
  memory_id: number | null
  message_id: number | null
  tokens: number
  error: string
  started_at: string
  finished_at: string | null
}

export interface HeartbeatEventData {
  run_id: number
  type: string
  character_id: number
  conversation_id: number | null
  message?: string
  monologue?: string
}

export interface HeartbeatEvent {
  type: 'heartbeat'
  data: HeartbeatEventData
}
