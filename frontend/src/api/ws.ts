import type { HeartbeatEvent } from '../types/heartbeat'

export type WsStatus = 'connecting' | 'open' | 'closed'

export interface WsHandlers {
  onEvent: (event: HeartbeatEvent) => void
  onStatus?: (status: WsStatus) => void
}

export interface HeartbeatSocket {
  close: () => void
}

const MAX_DELAY_MS = 30_000

/**
 * 心跳事件 WS 客户端：断线自动重连（指数退避 1s→2s→…→30s 封顶）。
 * 服务端空闲会发 {"type":"ping"}，这里回 {"type":"pong"} 保活。
 */
export function openHeartbeatSocket(
  params: { characterId?: number | null; conversationId?: number | null },
  handlers: WsHandlers
): HeartbeatSocket {
  let closed = false
  let retries = 0
  let ws: WebSocket | null = null
  let timer: number | null = null

  function buildUrl(): string {
    const qs = new URLSearchParams()
    if (params.characterId != null) qs.set('character_id', String(params.characterId))
    if (params.conversationId != null) qs.set('conversation_id', String(params.conversationId))
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const query = qs.toString()
    return `${scheme}://${location.host}/api/v1/ws${query ? `?${query}` : ''}`
  }

  function connect(): void {
    if (closed) return
    handlers.onStatus?.('connecting')
    ws = new WebSocket(buildUrl())

    ws.onopen = () => {
      retries = 0
      handlers.onStatus?.('open')
    }

    ws.onmessage = (ev) => {
      let data: any
      try {
        data = JSON.parse(ev.data)
      } catch {
        return
      }
      if (data?.type === 'ping') {
        // 服务端保活 ping：回 pong（服务端收任意消息即重置空闲计时）
        ws?.send(JSON.stringify({ type: 'pong' }))
        return
      }
      if (data?.type === 'heartbeat') handlers.onEvent(data as HeartbeatEvent)
    }

    ws.onclose = () => {
      handlers.onStatus?.('closed')
      if (closed) return
      retries += 1
      const delay = Math.min(1000 * 2 ** (retries - 1), MAX_DELAY_MS)
      timer = window.setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  connect()

  return {
    close(): void {
      closed = true
      if (timer !== null) window.clearTimeout(timer)
      ws?.close()
    }
  }
}
