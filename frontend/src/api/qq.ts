import type {
  QqBinding,
  QqBindingPayload,
  QqConversationSummary,
  QqGroup,
  QqMember,
  QqReply,
  QqStatus
} from '../types/qq'
import { del, get, patch, post } from './client'

export function getQqStatus(): Promise<QqStatus> {
  return get<QqStatus>('/qq/status')
}

export function listQqGroups(botUin = ''): Promise<QqGroup[]> {
  const suffix = botUin ? `?bot_uin=${encodeURIComponent(botUin)}` : ''
  return get<QqGroup[]>(`/qq/groups${suffix}`)
}

export function listQqBindings(characterId?: number): Promise<QqBinding[]> {
  const suffix = characterId ? `?character_id=${characterId}` : ''
  return get<QqBinding[]>(`/qq/bindings${suffix}`)
}

export function createQqBinding(payload: QqBindingPayload): Promise<QqBinding> {
  return post<QqBinding>('/qq/bindings', payload)
}

export function updateQqBinding(id: number, payload: Partial<QqBindingPayload>): Promise<QqBinding> {
  return patch<QqBinding>(`/qq/bindings/${id}`, payload)
}

export function deleteQqBinding(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/qq/bindings/${id}`)
}

export function listQqMembers(bindingId: number, search = ''): Promise<QqMember[]> {
  const suffix = search ? `?search=${encodeURIComponent(search)}` : ''
  return get<QqMember[]>(`/qq/bindings/${bindingId}/members${suffix}`)
}

export function updateQqMember(
  id: number,
  payload: { tags?: string[]; note?: string; ignored?: boolean }
): Promise<QqMember> {
  return patch<QqMember>(`/qq/members/${id}`, payload)
}

export function listQqReplies(bindingId: number, limit = 30): Promise<QqReply[]> {
  return get<QqReply[]>(`/qq/bindings/${bindingId}/replies?limit=${limit}`)
}

export function sendQqTest(
  bindingId: number,
  payload: { text: string; at_user_id?: string }
): Promise<{ ok: boolean; qq_message_id: string }> {
  return post<{ ok: boolean; qq_message_id: string }>(`/qq/bindings/${bindingId}/send`, payload)
}

export function getQqConversation(bindingId: number): Promise<QqConversationSummary | null> {
  return get<QqConversationSummary | null>(`/qq/bindings/${bindingId}/conversation`)
}
