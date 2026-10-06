import type { ModelRoute, ProviderConfig, RoutePayload } from '../types/provider'
import { del, get, post, put } from './client'

export function listProviders(): Promise<ProviderConfig[]> {
  return get<ProviderConfig[]>('/providers')
}

export interface ProviderPayload {
  name: string
  type: string
  base_url: string
  api_key?: string | null
  models: string[]
  is_default: boolean
  embedding_model?: string | null
  is_embedding_default?: boolean
}

export function createProvider(payload: ProviderPayload): Promise<ProviderConfig> {
  return post<ProviderConfig>('/providers', payload)
}

export function updateProvider(id: number, payload: Partial<ProviderPayload>): Promise<ProviderConfig> {
  return put<ProviderConfig>(`/providers/${id}`, payload)
}

export function deleteProvider(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/providers/${id}`)
}

export function listRoutes(): Promise<ModelRoute[]> {
  return get<ModelRoute[]>('/providers/routes')
}

export function setRoute(capability: string, payload: RoutePayload): Promise<ModelRoute> {
  return put<ModelRoute>(`/providers/routes/${capability}`, payload)
}

export function clearRoute(capability: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/providers/routes/${capability}`)
}

export async function testProvider(
  payload: Partial<ProviderPayload> & { id?: number; capability?: string }
): Promise<{ ok: boolean; models?: string[]; model?: string; dim?: number; error?: string }> {
  return post('/providers/test', payload)
}

export async function testEmbedding(
  payload: Partial<ProviderPayload> & { id?: number }
): Promise<{ ok: boolean; model?: string; dim?: number; error?: string }> {
  return post('/providers/test-embedding', payload)
}
