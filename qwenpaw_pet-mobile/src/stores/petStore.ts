import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PetState, Config, ChatMessage } from '../types'
import { DEFAULT_CONFIG, STORAGE_KEY } from '../types'

export const usePetStore = defineStore('pet', () => {
  // ── 配置 ──
  const config = ref<Config>(loadConfig())

  function loadConfig(): Config {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) return { ...DEFAULT_CONFIG, ...JSON.parse(raw) }
    } catch { /* ignore */ }
    return { ...DEFAULT_CONFIG }
  }

  function saveConfig() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config.value))
  }

  function updateConfig(partial: Partial<Config>) {
    Object.assign(config.value, partial)
    saveConfig()
  }

  // ── 宠物状态 ──
  const petState = ref<PetState>('silent')

  function setPetState(state: PetState) {
    petState.value = state
  }

  // ── 连接状态 ──
  const connected = ref(false)

  // ── 聊天消息 ──
  const messages = ref<ChatMessage[]>([])
  let msgCounter = 0

  function addUserMessage(content: string) {
    messages.value.push({
      id: `user-${++msgCounter}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    })
  }

  function addAssistantMessage(content: string) {
    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'assistant') {
      // 追加到上一条助手消息（流式累积）
      const updated = { ...last, content: last.content + content }
      messages.value[messages.value.length - 1] = updated
    } else {
      messages.value.push({
        id: `ai-${++msgCounter}`,
        role: 'assistant',
        content,
        timestamp: Date.now(),
      })
    }
  }

  function finishAssistantMessage() {
    // 流式结束 - 标记完成（目前无需额外操作）
  }

  function clearMessages() {
    messages.value = []
  }

  // ── UI 状态 ──
  const settingsOpen = ref(false)
  const menuOpen = ref(false)
  const textBoxExpanded = ref(false)
  const loading = ref(true)

  // ── 消息累积（流式缓冲区） ──
  const streamingText = ref('')

  // ── 计算属性 ──
  const lastAssistantMessage = computed(() => {
    return [...messages.value].reverse().find(m => m.role === 'assistant')
  })

  return {
    config, updateConfig,
    petState, setPetState,
    connected,
    messages, addUserMessage, addAssistantMessage, finishAssistantMessage, clearMessages,
    settingsOpen, menuOpen, textBoxExpanded, loading,
    streamingText,
    lastAssistantMessage,
  }
})
