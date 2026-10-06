export interface CharacterCard {
  name: string
  description: string
  personality: string
  scenario: string
  first_mes: string
  mes_example: string
  system_prompt: string
  tags: string[]
  avatar: string
  version: string
}

export interface CharacterExt {
  model?: {
    provider?: number | null
    model?: string
    temperature?: number
    max_tokens?: number
  }
  memory?: {
    window?: number
    top_k?: number
    half_life_days?: number
    summarize_every?: number
  }
  heartbeat?: {
    enabled?: boolean
    interval_min?: number
    type?: string[]
  }
  knowledge?: {
    collection?: string
    top_k?: number
  }
}

export interface Character {
  id: number
  name: string
  schema_version: string
  card: CharacterCard
  ext: CharacterExt
  avatar: string | null
  created_at: string
  updated_at: string
}

export function emptyCard(): CharacterCard {
  return {
    name: '',
    description: '',
    personality: '',
    scenario: '',
    first_mes: '',
    mes_example: '',
    system_prompt: '',
    tags: [],
    avatar: '',
    version: '1'
  }
}