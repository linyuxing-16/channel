/** 宠物状态 */
export type PetState = 'silent' | 'thinking' | 'speaking'

/** 配置项 */
export interface Config {
  url: string
  token: string
  streaming: boolean
  wake_word: string
  silence_timeout: number
  voice_enabled: boolean
}

/** 默认配置 */
export const DEFAULT_CONFIG: Config = {
  url: 'ws://localhost:8765',
  token: '',
  streaming: true,
  wake_word: '你好',
  silence_timeout: 3,
  voice_enabled: true,
}

/** WebSocket 消息（客户端→服务端） */
export interface ClientMessage {
  type: 'text'
  content: string
  session_id?: string
}

/** WebSocket 消息（服务端→客户端） */
export interface ServerMessage {
  type: 'connected' | 'stream_start' | 'stream_delta' | 'stream_end' | 'message' | 'error'
  text?: string
  client_id?: string
  streaming?: boolean
}

/** 聊天消息（UI 展示） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

/** Live2D 表情配置 */
export const STATE_TO_EXPRESSION: Record<PetState, string> = {
  silent: 'idle',
  thinking: 'think',
  speaking: 'speak',
}

/** 本地存储 key */
export const STORAGE_KEY = 'qwenpaw_pet_config'
