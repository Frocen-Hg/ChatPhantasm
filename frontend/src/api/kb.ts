import type {
  KbChunk,
  KbDocument,
  KbLore,
  KbLoreCreate,
  KbSearchResult
} from '../types/kb'
import { del, get, patch, post } from './client'

export function listDocuments(characterId: number): Promise<KbDocument[]> {
  return get<KbDocument[]>(`/kb/characters/${characterId}/documents`)
}

export function createDocument(
  characterId: number,
  payload: { title: string; text: string; scope?: string; visibility?: string }
): Promise<KbDocument> {
  return post<KbDocument>(`/kb/characters/${characterId}/documents`, payload)
}

/** 上传走 multipart，不能带 client 的 JSON Content-Type（浏览器需自动生成 boundary） */
export async function uploadDocument(
  characterId: number,
  file: File,
  scope = 'world',
  visibility = 'public'
): Promise<KbDocument> {
  const form = new FormData()
  form.append('file', file)
  const qs = `?scope=${encodeURIComponent(scope)}&visibility=${encodeURIComponent(visibility)}`
  const resp = await fetch(`/api/v1/kb/characters/${characterId}/documents/upload${qs}`, {
    method: 'POST',
    body: form
  })
  if (!resp.ok) {
    let detail = `请求失败: ${resp.status}`
    try {
      detail = (await resp.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<KbDocument>
}

export function listChunks(documentId: number): Promise<KbChunk[]> {
  return get<KbChunk[]>(`/kb/documents/${documentId}/chunks`)
}

export function deleteDocument(documentId: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/kb/documents/${documentId}`)
}

export function reindexDocument(documentId: number): Promise<KbDocument> {
  return post<KbDocument>(`/kb/documents/${documentId}/reindex`, {})
}

export function listLore(characterId: number): Promise<KbLore[]> {
  return get<KbLore[]>(`/kb/characters/${characterId}/lore`)
}

export function createLore(characterId: number, payload: KbLoreCreate): Promise<KbLore> {
  return post<KbLore>(`/kb/characters/${characterId}/lore`, payload)
}

export function updateLore(loreId: number, payload: Partial<KbLoreCreate>): Promise<KbLore> {
  return patch<KbLore>(`/kb/lore/${loreId}`, payload)
}

export function deleteLore(loreId: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/kb/lore/${loreId}`)
}

export function searchKnowledge(
  characterId: number,
  query: string,
  budgetTokens?: number
): Promise<KbSearchResult> {
  return post<KbSearchResult>('/kb/search', {
    character_id: characterId,
    query,
    budget_tokens: budgetTokens ?? null
  })
}
