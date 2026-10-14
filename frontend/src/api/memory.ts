import type {
  CharacterState,
  ContextPreview,
  Memory,
  MemoryCreate,
  MemorySearchResponse,
  MemoryUpdate,
  StateUpdate
} from '../types/memory'
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

export function updateCharacterState(
  characterId: number,
  payload: StateUpdate
): Promise<CharacterState> {
  return patch<CharacterState>(`/memory/characters/${characterId}/state`, payload)
}

export function decayMemories(characterId: number): Promise<{ archived: number }> {
  return post<{ archived: number }>(`/memory/characters/${characterId}/decay`, {})
}

export function searchMemories(
  characterId: number,
  query: string,
  topK = 6
): Promise<MemorySearchResponse> {
  return post<MemorySearchResponse>('/memory/search', {
    character_id: characterId,
    query,
    top_k: topK
  })
}

export function previewContext(
  characterId: number,
  query = '',
  conversationId?: number | null
): Promise<ContextPreview> {
  return post<ContextPreview>('/memory/context-preview', {
    character_id: characterId,
    query,
    conversation_id: conversationId ?? null
  })
}
