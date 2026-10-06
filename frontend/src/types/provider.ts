export interface ProviderConfig {
  id: number
  name: string
  type: string
  base_url: string
  models: string[]
  is_default: boolean
  api_key_masked?: string
}