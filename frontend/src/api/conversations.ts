import { del, get } from './client'

export interface Conversation {
  id: number
  character_id: number
  title: string
  message_count: number
  last_message: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  role: string
  content: string
  created_at: string
}

export function listConversations(characterId: number): Promise<Conversation[]> {
  return get<Conversation[]>(`/conversations?character_id=${characterId}`)
}

export function getMessages(conversationId: number): Promise<ChatMessage[]> {
  return get<ChatMessage[]>(`/conversations/${conversationId}/messages`)
}

export function deleteConversation(conversationId: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/conversations/${conversationId}`)
}