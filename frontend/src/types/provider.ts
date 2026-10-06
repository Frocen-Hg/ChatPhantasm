export interface ProviderConfig {
  id: number
  name: string
  type: string
  base_url: string
  models: string[]
  is_default: boolean
  is_embedding_default: boolean
  embedding_model: string | null
  api_key_masked?: string
}

export interface ModelRoute {
  capability: string // chat | embedding | ...
  provider_id: number
  provider_name?: string | null
  model: string
  params: Record<string, unknown>
  enabled: boolean
}

export interface RoutePayload {
  provider_id: number
  model?: string
  params?: Record<string, unknown>
  enabled?: boolean
}
