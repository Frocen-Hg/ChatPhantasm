export type QqReplyMode = 'mention' | 'keyword' | 'ambient' | 'all'

export interface QqBinding {
  id: number
  character_id: number
  character_name: string
  bot_uin: string
  group_id: string
  group_name: string
  conversation_id: number | null
  enabled: boolean
  reply_mode: QqReplyMode
  keywords: string[]
  reply_probability: number
  min_interval_sec: number
  max_replies_per_hour: number
  max_replies_per_day: number
  debounce_sec: number
  mention_bypass_cooldown: boolean
  proactive_enabled: boolean
  group_note: string
  last_active_at: string | null
  created_at: string
  updated_at: string
  member_count: number
  hour_replies: number
  day_replies: number
  last_reply_at: string | null
  connected: boolean
}

export interface QqBindingPayload {
  character_id: number
  group_id: string
  bot_uin?: string
  group_name?: string
  enabled?: boolean
  reply_mode?: QqReplyMode
  keywords?: string[]
  reply_probability?: number
  min_interval_sec?: number
  max_replies_per_hour?: number
  max_replies_per_day?: number
  debounce_sec?: number
  mention_bypass_cooldown?: boolean
  proactive_enabled?: boolean
  group_note?: string
}

export interface QqMember {
  id: number
  binding_id: number
  user_id: string
  nickname: string
  card: string
  display_name: string
  role: string
  tags: string[]
  note: string
  ignored: boolean
  message_count: number
  last_message_at: string | null
}

export interface QqReply {
  id: number
  binding_id: number
  conversation_id: number | null
  user_id: string
  trigger: string
  message_id: number | null
  content: string
  created_at: string
}

export interface QqBotStatus {
  self_id: string
  connected_at: string
  last_event_at: string | null
}

export interface QqStatus {
  connected: boolean
  bots: QqBotStatus[]
  bindings: number
  enabled_bindings: number
}

export interface QqGroup {
  group_id: string
  group_name: string
  member_count?: number
  max_member_count?: number
}

export interface QqConversationSummary {
  id: number
  title: string
  character_id: number
  message_count: number
  updated_at: string
}
