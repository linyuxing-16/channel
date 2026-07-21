<template>
  <div class="galgame-scene">
    <!-- 背景层 -->
    <div class="background-layer" :style="bgStyle">
      <div class="bg-overlay" />
    </div>

    <!-- Live2D 角色层 -->
    <div class="character-layer">
      <Live2DCanvas
        :model-path="modelPath"
        :fallback-src="fallbackSrc"
        @tap="onCharacterTap"
      />
    </div>

    <!-- 底部文字框 -->
    <TextBox
      :connected="connected"
      @send="onSend"
    />

    <!-- 右上角菜单 -->
    <MenuOverlay
      :connected="connected"
      @open-settings="onOpenSettings"
      @disconnect="onDisconnect"
    />

    <!-- 状态指示器 -->
    <div class="status-bar">
      <span class="status-dot" :class="{ active: connected }" />
      <span class="status-text">{{ connected ? '已连接' : '未连接' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePetStore } from '../stores/petStore'
import Live2DCanvas from './Live2DCanvas.vue'
import TextBox from './TextBox.vue'
import MenuOverlay from './MenuOverlay.vue'

const props = defineProps<{
  modelPath?: string
  fallbackSrc?: string
  connected: boolean
  backgroundImage?: string
  backgroundColor?: string
}>()

const emit = defineEmits<{
  send: [text: string]
  'open-settings': []
  disconnect: []
}>()

const store = usePetStore()

const bgStyle = computed(() => ({
  backgroundImage: props.backgroundImage ? `url(${props.backgroundImage})` : undefined,
  backgroundColor: props.backgroundColor || '#1a1a2e',
}))

// ── 事件转发 ──

function onSend(text: string) {
  emit('send', text)
}

function onCharacterTap(_x: number, _y: number) {
  // 点击角色展开输入框
  store.textBoxExpanded = true
}

function onOpenSettings() {
  store.settingsOpen = true
  emit('open-settings')
}

function onDisconnect() {
  emit('disconnect')
}
</script>

<style scoped>
.galgame-scene {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.background-layer {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.bg-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(0,0,0,0) 50%,
    rgba(0,0,0,0.4) 100%
  );
}

.character-layer {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 80px; /* 为文本框留空间 */
}

.status-bar {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 20;
  background: rgba(0,0,0,0.5);
  padding: 4px 10px;
  border-radius: 12px;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff6b6b;
  transition: background 0.3s;
}

.status-dot.active {
  background: #51cf66;
  box-shadow: 0 0 6px rgba(81, 207, 102, 0.6);
}

.status-text {
  font-size: 11px;
  color: rgba(255,255,255,0.7);
  font-family: 'Noto Sans SC', sans-serif;
}
</style>
