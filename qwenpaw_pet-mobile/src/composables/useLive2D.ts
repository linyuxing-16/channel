import { ref, onBeforeUnmount } from 'vue'
import * as PIXI from 'pixi.js'

/**
 * Live2D 模型控制 composable
 * 封装 pixi-live2d-display 的加载、表情切换、动画播放
 */
export function useLive2D() {
  let app: PIXI.Application | null = null
  let model: any = null
  let coreInitialized = false

  const modelLoaded = ref(false)
  const modelError = ref<string | null>(null)

  // ── 初始化 PIXI + Live2D Core ──

  async function init(canvas: HTMLCanvasElement, width: number, height: number) {
    // 初始化 Live2D Core（仅一次）
    if (!coreInitialized) {
      try {
        // Live2D Cubism Core 需要手动从官网下载放到 src/lib/ 目录
        // 开发阶段使用动态加载，若文件不存在则使用 fallback 模式
        const coreModule = await loadLive2DCore()
        if (coreModule) {
          const { initCDN } = await import('pixi-live2d-display')
          initCDN(coreModule)
          coreInitialized = true
        }
      } catch (e) {
        console.warn('[Live2D] Core not available, using fallback images:', e)
      }
    }

    // 创建 PIXI Application
    app = new PIXI.Application({
      view: canvas,
      width,
      height,
      backgroundAlpha: 0,
      backgroundColor: 0x000000,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    })
  }

  // 延迟加载 Live2D Core（文件可能不存在）
  async function loadLive2DCore(): Promise<any> {
    try {
      // 尝试从多个路径加载
      const paths = [
        '../lib/live2dcubismcore.min.js',
        '/live2dcubismcore.min.js',
        './live2dcubismcore.min.js',
      ]
      for (const p of paths) {
        try {
          const mod = await import(/* @vite-ignore */ p)
          if (mod?.Live2DCubismCore || mod?.default) {
            return mod.Live2DCubismCore || mod.default
          }
        } catch { /* try next */ }
      }
      return null
    } catch {
      return null
    }
  }

  // ── 加载模型 ──

  async function loadModel(modelPath: string) {
    if (!app) return

    modelError.value = null
    modelLoaded.value = false

    try {
      const { Live2DModel } = await import('pixi-live2d-display')
      model = await Live2DModel.from(modelPath)
      app.stage.addChild(model)

      // 居中并缩放模型
      const scaleX = app.screen.width / model.width
      const scaleY = app.screen.height / model.height
      const scale = Math.min(scaleX, scaleY) * 0.85
      model.scale.set(scale)
      model.anchor.set(0.5, 1)
      model.position.set(app.screen.width / 2, app.screen.height)

      modelLoaded.value = true
      console.log('[Live2D] Model loaded:', modelPath)

      // 播放默认待机动画
      playMotion('idle')
    } catch (e) {
      modelError.value = `Failed to load model: ${e}`
      console.error('[Live2D] Load error:', e)
    }
  }

  // ── 表情切换 ──

  async function setExpression(name: string) {
    if (!model) return
    try {
      if (model.expression) {
        await model.expression(name)
      }
    } catch (e) {
      // 表情不存在时忽略
      console.warn('[Live2D] Expression not found:', name)
    }
  }

  // ── 播放动作 ──

  async function playMotion(name: string, index?: number) {
    if (!model) return
    try {
      if (model.motion) {
        await model.motion(name, index ?? 0)
      }
    } catch (e) {
      console.warn('[Live2D] Motion not found:', name)
    }
  }

  // ── 口型同步 ──

  function setLipSync(enabled: boolean, value?: number) {
    if (!model) return
    if (model.lipSync !== undefined) {
      model.lipSync = enabled
      if (value !== undefined) {
        model.lipSyncValue = value
      }
    }
  }

  // ── 触摸交互 ──

  function onTap(x: number, y: number) {
    if (!model) return
    // 将屏幕坐标转换为模型本地坐标
    const local = model.toLocal(new PIXI.Point(x, y))
    model.focus(local.x, local.y)
    playMotion('tap_body').catch(() => {})
  }

  // ── 窗口大小变化 ──

  function resize(width: number, height: number) {
    if (!app) return
    app.renderer.resize(width, height)
    if (model) {
      const scaleX = width / model.width
      const scaleY = height / model.height
      const scale = Math.min(scaleX, scaleY) * 0.85
      model.scale.set(scale)
      model.position.set(width / 2, height)
    }
  }

  // ── 清理 ──

  function destroy() {
    if (model) {
      model.destroy()
      model = null
    }
    if (app) {
      app.destroy(true, { children: true })
      app = null
    }
    modelLoaded.value = false
    modelError.value = null
  }

  return {
    modelLoaded,
    modelError,
    init,
    loadModel,
    setExpression,
    playMotion,
    setLipSync,
    onTap,
    resize,
    destroy,
  }
}
