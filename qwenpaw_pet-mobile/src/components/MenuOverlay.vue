<template>
  <div class="menu-overlay">
    <!-- 设置按钮 -->
    <button class="menu-btn" @click="openMenu" aria-label="菜单">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    </button>

    <!-- 下拉菜单 -->
    <Teleport to="body">
      <div v-if="showMenu" class="menu-backdrop" @click.self="closeMenu">
        <div class="menu-sheet">
          <div class="menu-header">
            <span class="menu-title">菜单</span>
            <button class="close-btn" @click="closeMenu">✕</button>
          </div>

          <div class="menu-items">
            <button class="menu-item" @click="onSettings">
              <span class="item-icon">⚙️</span>
              <span class="item-label">设置</span>
            </button>

            <button class="menu-item" @click="onDisconnect">
              <span class="item-icon">{{ connected ? '🔌' : '🔗' }}</span>
              <span class="item-label">{{ connected ? '断开连接' : '重新连接' }}</span>
            </button>

            <button class="menu-item" @click="onClearMessages">
              <span class="item-icon">🗑️</span>
              <span class="item-label">清除对话</span>
            </button>
          </div>

          <div class="menu-footer">
            <span class="version">v1.0.0</span>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { usePetStore } from '../stores/petStore'

defineProps<{
  connected: boolean
}>()

const emit = defineEmits<{
  'open-settings': []
  disconnect: []
}>()

const store = usePetStore()
const showMenu = ref(false)

function openMenu() {
  showMenu.value = true
}

function closeMenu() {
  showMenu.value = false
}

function onSettings() {
  closeMenu()
  emit('open-settings')
}

function onDisconnect() {
  closeMenu()
  emit('disconnect')
}

function onClearMessages() {
  store.clearMessages()
  closeMenu()
}
</script>

<style scoped>
.menu-overlay {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 15;
}

.menu-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 50%;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.menu-btn:active {
  transform: scale(0.9);
  background: rgba(0,0,0,0.6);
}

/* Teleport 到 body 的全屏菜单 */
:global(.menu-backdrop) {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: flex-end;
  animation: fadeIn 0.2s ease;
}

.menu-sheet {
  width: 100%;
  background: rgba(30,30,50,0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px 20px 0 0;
  padding: 20px 24px;
  padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
  animation: slideUp 0.3s ease;
}

.menu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.menu-title {
  font-size: 18px;
  font-weight: 700;
  color: rgba(255,255,255,0.9);
  font-family: 'Noto Sans SC', sans-serif;
}

.close-btn {
  border: none;
  background: none;
  font-size: 20px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px;
}

.menu-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border: none;
  background: transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s;
  width: 100%;
  text-align: left;
}

.menu-item:active {
  background: rgba(255,255,255,0.08);
}

.item-icon {
  font-size: 20px;
  width: 28px;
  text-align: center;
}

.item-label {
  font-size: 16px;
  color: rgba(255,255,255,0.85);
  font-family: 'Noto Sans SC', sans-serif;
}

.menu-footer {
  margin-top: 20px;
  text-align: center;
}

.version {
  font-size: 12px;
  color: rgba(255,255,255,0.3);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
</style>
