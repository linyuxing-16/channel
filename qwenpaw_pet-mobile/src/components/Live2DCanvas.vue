<template>
  <div class="live2d-container" ref="containerRef" @click="onClick">
    <canvas ref="canvasRef" class="live2d-canvas" />
    <div v-if="modelError" class="model-error">
      {{ modelError }}
    </div>
    <!-- 当 Live2D 模型未加载时显示备用图片 -->
    <img
      v-if="!modelLoaded && !modelError && fallbackSrc"
      :src="fallbackSrc"
      class="fallback-image"
      :class="fallbackClass"
      alt="pet"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useLive2D } from '../composables/useLive2D'
import { usePetStore } from '../stores/petStore'
import { STATE_TO_EXPRESSION } from '../types'

const props = defineProps<{
  modelPath?: string
  fallbackSrc?: string
}>()

const emit = defineEmits<{
  tap: [x: number, y: number]
}>()

const store = usePetStore()
const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const { modelLoaded, modelError, init, loadModel, setExpression, playMotion, onTap, resize, destroy } = useLive2D()

const fallbackClass = ref('')

// ── 生命周期 ──

onMounted(async () => {
  if (!canvasRef.value || !containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  await init(canvasRef.value, rect.width, rect.height)

  // 加载 Live2D 模型
  if (props.modelPath) {
    await loadModel(props.modelPath)
    // 初始表情
    setExpression('idle').catch(() => {})
  }
})

onBeforeUnmount(() => {
  destroy()
})

// ── 监听宠物状态 → 切换 Live2D 表情/动画 ──

watch(() => store.petState, async (state) => {
  if (!modelLoaded.value) {
    // 无 Live2D 时，用 CSS class 模拟状态
    fallbackClass.value = state === 'thinking' ? 'thinking' : state === 'speaking' ? 'speaking' : ''
    return
  }

  const expr = STATE_TO_EXPRESSION[state]
  await setExpression(expr)

  switch (state) {
    case 'silent':
      playMotion('idle').catch(() => {})
      break
    case 'thinking':
      playMotion('think').catch(() => {})
      break
    case 'speaking':
      playMotion('speak').catch(() => {})
      break
  }
})

// ── 点击事件 ──

function onClick(event: MouseEvent | TouchEvent) {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX
  const clientY = 'touches' in event ? event.touches[0].clientY : event.clientY
  const x = clientX - rect.left
  const y = clientY - rect.top
  onTap(x, y)
  emit('tap', x, y)
}

// ── resize ──

function handleResize() {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  resize(rect.width, rect.height)
}

window.addEventListener('resize', handleResize)
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))
</script>

<style scoped>
.live2d-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.fallback-image {
  max-width: 85%;
  max-height: 85%;
  object-fit: contain;
  transition: transform 0.3s ease, filter 0.3s ease;
  user-select: none;
  -webkit-user-drag: none;
}

.fallback-image.thinking {
  transform: scale(0.95);
  filter: brightness(0.8) saturate(0.6);
  animation: pulse 1.5s ease-in-out infinite;
}

.fallback-image.speaking {
  animation: speak-bounce 0.3s ease-in-out infinite alternate;
}

.model-error {
  position: absolute;
  bottom: 20px;
  left: 20px;
  right: 20px;
  color: #ff6b6b;
  background: rgba(0,0,0,0.7);
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  text-align: center;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes speak-bounce {
  0% { transform: translateY(0); }
  100% { transform: translateY(-5px); }
}
</style>
