import type { CharacterState, Memory, MemoryCreate, MemoryUpdate } from '../types/memory'
import { del, get, patch, post } from './client'

export function listMemories(
  characterId: number,
  params?: { layer?: string; kind?: string }
): Promise<Memory[]> {
  const qs = new URLSearchParams()
  if (params?.layer) qs.set('layer', params.layer)
  if (params?.kind) qs.set('kind', params.kind)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return get<Memory[]>(`/memory/characters/${characterId}/memories${suffix}`)
}

export function createMemory(characterId: number, payload: MemoryCreate): Promise<Memory> {
  return post<Memory>(`/memory/characters/${characterId}/memories`, payload)
}

export function updateMemory(memoryId: number, payload: MemoryUpdate): Promise<Memory> {
  return patch<Memory>(`/memory/memories/${memoryId}`, payload)
}

export function deleteMemory(memoryId: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/memory/memories/${memoryId}`)
}

export function getCharacterState(characterId: number): Promise<CharacterState> {
  return get<CharacterState>(`/memory/characters/${characterId}/state`)
}
