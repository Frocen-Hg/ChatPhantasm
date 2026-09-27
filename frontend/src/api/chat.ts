import type { ChatRequest } from '../types/chat'

export async function streamChat(payload: ChatRequest, onToken: (text: string) => void): Promise<number | null> {
  const resp = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!resp.ok || !resp.body) {
    let detail = `请求失败: ${resp.status}`
    try {
      const data = await resp.json()
      detail = data.detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  const convHeader = resp.headers.get('X-Conversation-Id')
  const conversationId = convHeader ? Number(convHeader) : null

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    onToken(decoder.decode(value, { stream: true }))
  }
  return conversationId
}