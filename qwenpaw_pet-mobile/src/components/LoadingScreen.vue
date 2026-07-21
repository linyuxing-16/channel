<template>
  <div class="loading-screen">
    <div class="loading-content">
      <div class="pet-icon" :class="state">
        <img v-if="iconSrc" :src="iconSrc" alt="pet" class="icon-img" />
        <div v-else class="icon-placeholder">🐾</div>
      </div>
      <p class="loading-text">{{ text }}</p>
      <div class="loading-bar">
        <div class="loading-progress" :style="{ width: progress + '%' }" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  text?: string
  progress?: number
  state?: 'silent' | 'thinking' | 'speaking'
  iconSrc?: string
}>()
</script>

<style scoped>
.loading-screen {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-content {
  text-align: center;
}

.pet-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.5s ease;
}

.pet-icon.speaking {
  animation: float 1s ease-in-out infinite;
}

.icon-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.icon-placeholder {
  font-size: 48px;
  animation: pulse 1.5s ease-in-out infinite;
}

.loading-text {
  font-size: 16px;
  color: rgba(255,255,255,0.7);
  margin-bottom: 20px;
  font-family: 'Noto Sans SC', sans-serif;
}

.loading-bar {
  width: 200px;
  height: 3px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
  margin: 0 auto;
}

.loading-progress {
  height: 100%;
  background: linear-gradient(90deg, #a8d8ea, #7ec8e3);
  border-radius: 2px;
  transition: width 0.3s ease;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.7; }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
</style>
