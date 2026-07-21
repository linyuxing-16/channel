import { ref } from 'vue'
import { usePetStore } from '../stores/petStore'
import type { ServerMessage, ClientMessage } from '../types'

/**
 * WebSocket 客户端 composable
 * 完全兼容 QwenpawPet 桌面版的 WebSocket 协议
 */
export function useWebSocket() {
  const store = usePetStore()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const MAX_RECONNECT_DELAY = 30000
  let reconnectAttempts = 0

  const connected = ref(false)

  // ── 连接 ──

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    const { url, token } = store.config
    if (!url) return

    // 浏览器 WebSocket API 不支持自定义请求头，
    // 将 token 以查询参数方式传递，服务端需支持此方式
    const wsUrl = new URL(url)
    if (token) {
      wsUrl.searchParams.set('token', token)
    }
    wsUrl.searchParams.set('streaming', store.config.streaming ? '1' : '0')

    try {
      ws = new WebSocket(wsUrl.toString())
    } catch (e) {
      console.error('[WebSocket] Connection failed:', e)
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      console.log('[WebSocket] Connected')
      connected.value = true
      store.connected = true
      reconnectAttempts = 0

      // 发送鉴权消息（兼容服务端的 Authorization 头方式）
      if (token) {
        ws?.send(JSON.stringify({
          type: 'auth',
          token: `Bearer ${token}`,
        }))
      }
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const raw = typeof event.data === 'string'
          ? event.data
          : new TextDecoder().decode(event.data as ArrayBuffer)
        handleMessage(JSON.parse(raw))
      } catch (e) {
        console.error('[WebSocket] Parse error:', e)
      }
    }

    ws.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason)
      connected.value = false
      store.connected = false
      ws = null
      if (event.code !== 1000) {
        scheduleReconnect()
      }
    }

    ws.onerror = (event) => {
      console.error('[WebSocket] Error:', event)
    }
  }

  // ── 消息处理 ──

  function handleMessage(msg: ServerMessage) {
    switch (msg.type) {
      case 'connected':
        console.log('[WebSocket] Handshake OK, client_id:', msg.client_id)
        break

      case 'stream_start':
        store.streamingText = ''
        break

      case 'stream_delta':
        if (msg.text) {
          store.streamingText += msg.text
          store.addAssistantMessage(msg.text)
          store.setPetState('speaking')
        }
        break

      case 'stream_end':
        if (msg.text) {
          // 确保最后一段也追加
          store.streamingText += msg.text
          store.addAssistantMessage(msg.text)
        }
        store.finishAssistantMessage()
        store.setPetState('silent')
        store.streamingText = ''
        break

      case 'message':
        // 非流式模式
        if (msg.text) {
          store.addAssistantMessage(msg.text)
          store.setPetState('speaking')
          // 非流式立即回到沉默
          setTimeout(() => store.setPetState('silent'), 100)
        }
        break

      case 'error':
        console.error('[WebSocket] Server error:', msg.text)
        break

      default:
        console.warn('[WebSocket] Unknown message type:', msg)
    }
  }

  // ── 发送 ──

  function sendText(text: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] Not connected')
      return false
    }

    const message: ClientMessage = {
      type: 'text',
      content: text,
    }

    ws.send(JSON.stringify(message))
    store.addUserMessage(text)
    store.setPetState('thinking')
    return true
  }

  function sendAudio(base64Data: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] Not connected')
      return false
    }

    const message = {
      type: 'text',
      content: [
        { type: 'audio', data: base64Data, format: 'wav' },
      ],
    }

    ws.send(JSON.stringify(message))
    store.setPetState('thinking')
    return true
  }

  // ── 重连 ──

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY)
    reconnectAttempts++
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  // ── 断开 ──

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close(1000, 'Client disconnect')
      ws = null
    }
    connected.value = false
    store.connected = false
  }

  return {
    connected,
    connect,
    disconnect,
    sendText,
    sendAudio,
  }
}
