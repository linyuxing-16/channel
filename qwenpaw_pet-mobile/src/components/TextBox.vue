<template>
  <div
    class="text-box"
    :class="{ expanded: store.textBoxExpanded, collapsed: !store.textBoxExpanded }"
    @click="expand"
  >
    <!-- 收起时的标题栏 -->
    <div v-if="!store.textBoxExpanded" class="text-box-bar">
      <span class="bar-label">点击输入消息</span>
      <span class="bar-indicator">▲</span>
    </div>

    <!-- 展开后的内容 -->
    <template v-if="store.textBoxExpanded">
      <!-- 对话历史 -->
      <div class="messages-area" ref="messagesRef">
        <div
          v-for="msg in store.messages"
          :key="msg.id"
          class="message"
          :class="msg.role"
        >
          <div class="message-content">
            <span v-if="msg.role === 'user'" class="label">你</span>
            <span v-else class="label pet-label">宠物</span>
            <span class="text">{{ msg.content }}</span>
          </div>
        </div>
        <!-- 流式光标 -->
        <div v-if="store.streamingText" class="message assistant">
          <div class="message-content">
            <span class="label pet-label">宠物</span>
            <span class="text">{{ store.streamingText }}<span class="cursor">▌</span></span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <input
          ref="inputRef"
          v-model="inputText"
          class="text-input"
          type="text"
          placeholder="输入消息..."
          @keydown.enter="send"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
        />
        <button class="send-btn" @click="send" :disabled="!inputText.trim() || !connected">
          发送
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { usePetStore } from '../stores/petStore'

const props = defineProps<{
  connected: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const store = usePetStore()
const inputText = ref('')
const inputRef = ref<HTMLInputElement>()
const messagesRef = ref<HTMLDivElement>()
const isComposing = ref(false)

// ── 发送消息 ──

function send() {
  const text = inputText.value.trim()
  if (!text || isComposing.value || !props.connected) return
  emit('send', text)
  inputText.value = ''
}

// ── 展开文本框 ──

function expand() {
  if (!store.textBoxExpanded) {
    store.textBoxExpanded = true
    nextTick(() => {
      inputRef.value?.focus()
      scrollToBottom()
    })
  }
}

// ── 自动滚动到底部 ──

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.streamingText, scrollToBottom)
</script>

<style scoped>
.text-box {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 10;
  transition: all 0.3s ease;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}

.text-box.collapsed {
  height: 40px;
  cursor: pointer;
}

.text-box.expanded {
  height: 45vh;
  max-height: 400px;
}

.text-box-bar {
  height: 40px;
  background: linear-gradient(180deg, rgba(0,0,0,0.3), rgba(0,0,0,0.8));
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-top: 1px solid rgba(255,255,255,0.15);
}

.bar-label {
  color: rgba(255,255,255,0.6);
  font-size: 14px;
}

.bar-indicator {
  color: rgba(255,255,255,0.4);
  font-size: 12px;
}

.messages-area {
  height: calc(100% - 52px);
  overflow-y: auto;
  padding: 12px 16px;
  background: linear-gradient(180deg, rgba(0,0,0,0.6), rgba(0,0,0,0.85));
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.2) transparent;
}

.message {
  margin-bottom: 12px;
  animation: fadeIn 0.3s ease;
}

.message.user .message-content {
  text-align: right;
}

.message.assistant .message-content {
  text-align: left;
}

.message-content .label {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  display: block;
  margin-bottom: 4px;
}

.pet-label {
  color: #a8d8ea !important;
}

.message-content .text {
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255,255,255,0.9);
  display: inline-block;
  background: rgba(255,255,255,0.08);
  padding: 6px 12px;
  border-radius: 12px;
  max-width: 90%;
  word-break: break-word;
}

.message.user .text {
  background: rgba(100, 180, 255, 0.2);
  border-bottom-right-radius: 4px;
}

.message.assistant .text {
  border-bottom-left-radius: 4px;
}

.cursor {
  animation: blink 0.8s step-end infinite;
  color: #a8d8ea;
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(0,0,0,0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-top: 1px solid rgba(255,255,255,0.1);
}

.text-input {
  flex: 1;
  height: 36px;
  border: none;
  outline: none;
  background: rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 0 16px;
  font-size: 14px;
  color: rgba(255,255,255,0.9);
  font-family: inherit;
}

.text-input::placeholder {
  color: rgba(255,255,255,0.3);
}

.send-btn {
  height: 36px;
  padding: 0 20px;
  border: none;
  border-radius: 18px;
  background: linear-gradient(135deg, #a8d8ea, #7ec8e3);
  color: #1a1a2e;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>
