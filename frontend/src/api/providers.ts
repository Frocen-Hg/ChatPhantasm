import type { ProviderConfig } from '../types/provider'
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

export async function testProvider(payload: Partial<ProviderPayload> & { id?: number }): Promise<{ ok: boolean; models?: string[]; error?: string }> {
  return post('/providers/test', payload)
}