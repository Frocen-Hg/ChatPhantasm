export interface Memory {
  id: number
  character_id: number
  conversation_id: number | null
  layer: string // L2 | L3 | L4
  kind: string // summary | fact | preference | relation | monologue | reflection
  content: string
  importance: number
  visibility: string // public | private
  access_count: number
  indexed?: boolean | null // true=已索引；false=应索引但缺失；null=不适用（L2/private/已归档）
  source_start_id?: number | null
  source_end_id?: number | null
  decay_at?: string | null
  meta: Record<string, unknown>
  created_at: string
}

export interface CharacterState {
  character_id: number
  mood: string
  arousal: number
  current_focus: string
  relationship: Record<string, unknown>
  last_user_at: string | null
  last_beat_at: string | null
  updated_at: string
}

export interface MemoryCreate {
  content: string
  kind?: string
  layer?: string
  importance?: number
  visibility?: string
}

export interface MemoryUpdate {
  content?: string
  kind?: string
  layer?: string
  importance?: number
  visibility?: string
}

export interface StateUpdate {
  mood?: string
  arousal?: number
  current_focus?: string
  relationship?: Record<string, unknown>
}

export interface MemorySearchResult {
  id: number
  layer: string
  kind: string
  content: string
  importance: number
  keyword: number
  vector: number | null
  recency: number
  score: number
  effective_importance: number
  tokens: number
}

export interface MemorySearchResponse {
  query: string
  results: MemorySearchResult[]
}

export interface ContextBlock {
  name: string
  content: string
  tokens: number
}

export interface ContextHistoryItem {
  role: string
  content: string
  tokens: number
}

export interface ContextPreview {
  query: string
  budget: number
  total_tokens: number
  blocks: ContextBlock[]
  history: ContextHistoryItem[]
  system: string
}
