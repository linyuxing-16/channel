<template>
  <div class="settings-page">
    <div class="page-header">
      <button class="back-btn" @click="goBack">← 返回</button>
      <h1 class="page-title">设置</h1>
    </div>

    <div class="page-body">
      <!-- 连接 -->
      <div class="section">
        <h3 class="section-title">连接</h3>
        <div class="field">
          <label class="field-label">URL</label>
          <input v-model="form.url" class="field-input" type="text" />
        </div>
        <div class="field">
          <label class="field-label">Token</label>
          <input v-model="form.token" class="field-input" type="password" />
        </div>
      </div>

      <!-- 对话 -->
      <div class="section">
        <h3 class="section-title">对话</h3>
        <div class="field-row">
          <span class="field-label">流式模式</span>
          <label class="toggle">
            <input v-model="form.streaming" type="checkbox" />
            <span class="toggle-slider" />
          </label>
        </div>
      </div>

      <!-- 语音 -->
      <div class="section">
        <h3 class="section-title">语音</h3>
        <div class="field-row">
          <span class="field-label">启用语音唤醒</span>
          <label class="toggle">
            <input v-model="form.voice_enabled" type="checkbox" />
            <span class="toggle-slider" />
          </label>
        </div>
        <div class="field">
          <label class="field-label">唤醒词</label>
          <input v-model="form.wake_word" class="field-input" type="text" />
        </div>
        <div class="field">
          <label class="field-label">静音超时（秒）</label>
          <input v-model.number="form.silence_timeout" class="field-input" type="number" min="1" max="30" />
        </div>
      </div>
    </div>

    <div class="page-footer">
      <button class="btn btn-save" @click="save">保存</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePetStore } from '../stores/petStore'

const router = useRouter()
const store = usePetStore()
const form = reactive({ ...store.config })

onMounted(() => {
  Object.assign(form, store.config)
})

function goBack() {
  router.back()
}

function save() {
  store.updateConfig({ ...form })
  router.back()
}
</script>

<style scoped>
.settings-page {
  width: 100%;
  height: 100%;
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  color: rgba(255,255,255,0.9);
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  padding-top: calc(16px + env(safe-area-inset-top, 0px));
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.back-btn {
  border: none;
  background: none;
  color: #a8d8ea;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 0;
  font-family: inherit;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}

.page-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.section {
  margin-bottom: 28px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #a8d8ea;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.field {
  margin-bottom: 14px;
}

.field-label {
  display: block;
  font-size: 14px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 6px;
}

.field-input {
  width: 100%;
  height: 42px;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.85);
  padding: 0 14px;
  font-size: 15px;
  outline: none;
  font-family: inherit;
}

.field-input:focus {
  border-color: #a8d8ea;
}

.field-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 26px;
  cursor: pointer;
}

.toggle input { display: none; }

.toggle-slider {
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.15);
  border-radius: 13px;
  transition: background 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 22px;
  height: 22px;
  left: 2px;
  top: 2px;
  background: white;
  border-radius: 50%;
  transition: transform 0.3s;
}

.toggle input:checked + .toggle-slider {
  background: #a8d8ea;
}

.toggle input:checked + .toggle-slider::before {
  transform: translateX(18px);
}

.page-footer {
  padding: 16px 20px;
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid rgba(255,255,255,0.06);
}

.btn {
  width: 100%;
  height: 46px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.btn-save {
  background: linear-gradient(135deg, #a8d8ea, #7ec8e3);
  color: #1a1a2e;
}

.btn:active {
  transform: scale(0.97);
}
</style>
