export interface KbDocument {
  id: number
  character_id: number
  title: string
  source_type: string // text | file
  source_uri: string
  scope: string // world | self | relation | rule
  visibility: string // public | private
  chunk_size: number
  chunk_overlap: number
  status: string // pending | indexed | failed
  error: string
  chunk_count: number
  indexed_count: number
  created_at: string
  updated_at: string
}

export interface KbChunk {
  id: number
  seq: number
  content: string
  tokens: number
  indexed: boolean
}

export interface KbLore {
  id: number
  character_id: number
  keys: string[]
  content: string
  constant: boolean
  priority: number
  scan_depth: number
  scope: string
  visibility: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface KbLoreCreate {
  content: string
  keys?: string[]
  constant?: boolean
  priority?: number
  scan_depth?: number | null
  scope?: string
  visibility?: string
  enabled?: boolean
}

export interface KbSearchLoreHit {
  id: number
  keys: string[]
  constant: boolean
  priority: number
  matched: string
  included: boolean
  content: string
  tokens: number
}

export interface KbSearchChunkHit {
  id: number
  document_id: number
  title: string
  seq: number
  scope: string
  included: boolean
  content: string
  score: number
  tokens: number
}

export interface KbSearchResult {
  query: string
  lore: KbSearchLoreHit[]
  chunks: KbSearchChunkHit[]
  block: string
  tokens: number
}
