<template>
  <div class="home">
    <!-- 加载屏幕 -->
    <LoadingScreen
      v-if="store.loading"
      :progress="loadProgress"
      text="正在连接..."
    />

    <!-- Galgame 主场景 -->
    <GalgameScene
      ref="sceneRef"
      :connected="wsConnected"
      :model-path="modelPath"
      :fallback-src="fallbackSrc"
      :background-image="bgImage"
      @send="handleSend"
      @open-settings="openSettings"
      @disconnect="handleDisconnect"
    />

    <!-- 设置 modal -->
    <SettingsModal
      :visible="store.settingsOpen"
      @close="store.settingsOpen = false"
      @saved="onSettingsSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { usePetStore } from '../stores/petStore'
import { useWebSocket } from '../composables/useWebSocket'
import GalgameScene from '../components/GalgameScene.vue'
import LoadingScreen from '../components/LoadingScreen.vue'
import SettingsModal from '../components/SettingsModal.vue'

const store = usePetStore()
const { connected: wsConnected, connect, disconnect, sendText } = useWebSocket()

const loadProgress = ref(0)
const modelPath = ref<string | undefined>(undefined)
const fallbackSrc = ref<string | undefined>(undefined)
const bgImage = ref<string | undefined>(undefined)

// ── 生命周期 ──

onMounted(async () => {
  // 模拟加载进度
  const timer = setInterval(() => {
    if (loadProgress.value < 90) {
      loadProgress.value += Math.random() * 15
    }
  }, 300)

  // 连接 WebSocket
  connect()

  // 尝试加载 Live2D 模型
  try {
    modelPath.value = '/live2d-models/hiyori/model.model3.json'
    loadProgress.value = 95
  } catch {
    // 无 Live2D 模型时使用备用图片
    fallbackSrc.value = '/live2d-models/hiyori/texture_00.png'
  }

  // 加载完成
  setTimeout(() => {
    loadProgress.value = 100
    setTimeout(() => {
      store.loading = false
    }, 400)
  }, 500)

  clearInterval(timer)
})

onBeforeUnmount(() => {
  disconnect()
})

// ── 发送消息 ──

function handleSend(text: string) {
  sendText(text)
}

// ── 设置 ──

function openSettings() {
  store.settingsOpen = true
}

function onSettingsSaved() {
  // 配置变更后重新连接
  disconnect()
  setTimeout(() => connect(), 300)
}

// ── 断开/重连 ──

function handleDisconnect() {
  if (wsConnected.value) {
    disconnect()
  } else {
    connect()
  }
}
</script>

<style scoped>
.home {
  width: 100%;
  height: 100%;
  position: relative;
  background: #1a1a2e;
}
</style>
