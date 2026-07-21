<template>
  <Teleport to="body">
    <div v-if="visible" class="settings-backdrop" @click.self="close">
      <div class="settings-sheet">
        <div class="settings-header">
          <h2 class="settings-title">设置</h2>
          <button class="close-btn" @click="close">✕</button>
        </div>

        <div class="settings-body">
          <!-- WebSocket 连接 -->
          <div class="section">
            <h3 class="section-title">连接</h3>

            <div class="field">
              <label class="field-label">URL</label>
              <input v-model="form.url" class="field-input" type="text" placeholder="ws://localhost:8765" />
            </div>

            <div class="field">
              <label class="field-label">Token</label>
              <input v-model="form.token" class="field-input" type="password" placeholder="Bearer token" />
            </div>
          </div>

          <!-- 对话 -->
          <div class="section">
            <h3 class="section-title">对话</h3>

            <div class="field-row">
              <label class="field-label">流式模式</label>
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
              <label class="field-label">启用语音唤醒</label>
              <label class="toggle">
                <input v-model="form.voice_enabled" type="checkbox" />
                <span class="toggle-slider" />
              </label>
            </div>

            <div class="field">
              <label class="field-label">唤醒词</label>
              <input v-model="form.wake_word" class="field-input" type="text" placeholder="你好" />
            </div>

            <div class="field">
              <label class="field-label">静音超时（秒）</label>
              <input v-model.number="form.silence_timeout" class="field-input" type="number" min="1" max="30" />
            </div>
          </div>
        </div>

        <div class="settings-footer">
          <button class="btn btn-cancel" @click="close">取消</button>
          <button class="btn btn-save" @click="save">保存</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { usePetStore } from '../stores/petStore'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const store = usePetStore()

const form = reactive({ ...store.config })

// 每次打开时同步表单
watch(() => props.visible, (v) => {
  if (v) Object.assign(form, store.config)
})

function close() {
  emit('close')
}

function save() {
  store.updateConfig({ ...form })
  emit('saved')
  close()
}
</script>

<style scoped>
.settings-backdrop {
  position: fixed;
  inset: 0;
  z-index: 900;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: flex-end;
  animation: fadeIn 0.2s ease;
}

.settings-sheet {
  width: 100%;
  max-height: 85vh;
  background: rgba(25,25,45,0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px 20px 0 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.settings-title {
  font-size: 20px;
  font-weight: 700;
  color: rgba(255,255,255,0.9);
  font-family: 'Noto Sans SC', sans-serif;
  margin: 0;
}

.close-btn {
  border: none;
  background: none;
  font-size: 22px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px 8px;
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.1) transparent;
}

.section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #a8d8ea;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.field {
  margin-bottom: 14px;
}

.field-label {
  display: block;
  font-size: 13px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 6px;
}

.field-input {
  width: 100%;
  height: 40px;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.85);
  padding: 0 14px;
  font-size: 15px;
  outline: none;
  font-family: inherit;
  transition: border-color 0.2s;
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

/* Toggle switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 26px;
  cursor: pointer;
}

.toggle input {
  display: none;
}

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

.settings-footer {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid rgba(255,255,255,0.06);
}

.btn {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Noto Sans SC', sans-serif;
}

.btn:active {
  transform: scale(0.97);
}

.btn-cancel {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.7);
}

.btn-save {
  background: linear-gradient(135deg, #a8d8ea, #7ec8e3);
  color: #1a1a2e;
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
