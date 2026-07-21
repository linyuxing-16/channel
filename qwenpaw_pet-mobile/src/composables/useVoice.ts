import { ref } from 'vue'
import { usePetStore } from '../stores/petStore'

/**
 * 语音唤醒 + 录音 composable
 * 使用 sherpa-onnx WASM 进行关键词唤醒 (KWS)
 * 
 * 注意：sherpa-onnx WASM 需从 GitHub Releases 手动下载，
 * 放在 public/sherpa-onnx-wasm/ 下通过 <script> 加载。
 * 此文件提供接口占位，sherpa-onnx WASM 就绪后接入。
 */
export function useVoice() {
  const store = usePetStore()
  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let audioStream: MediaStream | null = null
  let isListening = false

  const voiceActive = ref(false)
  const voiceError = ref<string | null>(null)

  // ── 检查浏览器支持 ──

  function isSupported(): boolean {
    return !!(
      typeof navigator.mediaDevices?.getUserMedia === 'function' &&
      typeof MediaRecorder !== 'undefined'
    )
  }

  // ── KWS 初始化（sherpa-onnx WASM 就绪后调用） ──

  async function initKWS(): Promise<boolean> {
    // 占位：等待 sherpa-onnx WASM 加载
    // 实际实现：
    // 1. 加载 sherpa-onnx-kws.js（已通过 <script> 标签引入）
    // 2. 使用 createKws() 初始化
    // 3. 设置回调
    console.log('[Voice] KWS init placeholder')
    return true
  }

  // ── 开始监听唤醒词 ──

  async function start() {
    if (!store.config.voice_enabled) return
    if (!isSupported()) {
      voiceError.value = '浏览器不支持语音功能'
      return
    }

    try {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      isListening = true
      voiceActive.value = true

      // 占位：启动 sherpa-onnx KWS 识别循环
      // 检测到唤醒词后调用 onWakeWord()
      console.log('[Voice] Listening for wake word:', store.config.wake_word)
    } catch (e: any) {
      voiceError.value = `麦克风访问失败: ${e.message}`
      console.error('[Voice] Mic error:', e)
    }
  }

  // ── 唤醒词回调 ──

  function onWakeWord() {
    console.log('[Voice] Wake word detected!')
    store.setPetState('thinking')
    startRecording()
  }

  // ── 开始录音 ──

  function startRecording() {
    if (!audioStream) return

    audioChunks = []
    mediaRecorder = new MediaRecorder(audioStream, {
      mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm',
    })

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }

    mediaRecorder.onstop = async () => {
      // 编码为 base64 WAV
      const blob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
      const base64 = await blobToBase64(blob)
      console.log('[Voice] Audio captured, size:', base64.length)

      // 占位：通过 WebSocket 发送
      // sendAudio(base64)
    }

    mediaRecorder.start()
    console.log('[Voice] Recording started')

    // 占位：启动 VAD 静音检测
    // 检测到静音超时 → stopRecording()
  }

  // ── 停止录音 ──

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
      console.log('[Voice] Recording stopped')
    }
  }

  // ── 停止所有 ──

  function stop() {
    isListening = false
    voiceActive.value = false
    stopRecording()
    if (audioStream) {
      audioStream.getTracks().forEach(t => t.stop())
      audioStream = null
    }
  }

  // ── 工具 ──

  function blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => {
        const result = reader.result as string
        // 去掉 data:...;base64, 前缀
        const base64 = result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(blob)
    })
  }

  return {
    voiceActive,
    voiceError,
    isSupported,
    initKWS,
    start,
    stop,
    onWakeWord,
    startRecording,
    stopRecording,
  }
}
