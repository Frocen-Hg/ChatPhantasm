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
