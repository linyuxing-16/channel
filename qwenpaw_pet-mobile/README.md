# Qwenpaw Pet Mobile

Galgame 风格的移动端桌面宠物，支持 Live2D 角色 + WebSocket 对话 + 语音唤醒。

基于 Vue 3 + Vite + Capacitor 构建，可打包为 Android/iOS 本地应用。

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式（浏览器）
npm run dev

# 构建生产版本
npm run build
```

## 设置 Live2D

需要手动下载 Live2D Cubism Core SDK：

1. 前往 [Live2D 官网](https://www.live2d.com/download/cubism-sdk/download-web/) 下载 Cubism 5 SDK for Web
2. 将 `live2dcubismcore.min.js` 复制到 `src/lib/`
3. 将 Live2D 模型文件放入 `public/live2d-models/<model-name>/`

开发阶段若没有 Live2D SDK，应用将使用备用图片模式运行。

## 设置语音唤醒

语音功能基于 sherpa-onnx WASM：

1. 从 [sherpa-onnx Releases](https://github.com/k2-fsa/sherpa-onnx/releases) 下载 WASM 包
2. 解压到 `public/sherpa-onnx-wasm/`
3. 在 `index.html` 中添加 `<script>` 标签加载

开发阶段若没有 sherpa-onnx WASM，语音功能将不可用，文本聊天不受影响。

## 原生打包

```bash
# 构建 Web 资源
npm run build

# 同步到原生平台
npx cap sync

# 运行 Android
npx cap run android

# 运行 iOS（需 macOS）
npx cap run ios
```

## 技术栈

| 层 | 技术 |
|---|------|
| 前端框架 | Vue 3 + TypeScript |
| 构建工具 | Vite |
| 状态管理 | Pinia |
| 渲染引擎 | PixiJS v7 |
| Live2D | pixi-live2d-display + Cubism SDK |
| 原生壳 | Capacitor |
| 语音 (KWS) | sherpa-onnx WASM |
| WebSocket | 原生 WebSocket API |

## 项目结构

```
src/
├── main.ts              # 入口
├── App.vue              # 根组件
├── router/              # 路由
├── stores/              # Pinia 状态管理
│   └── petStore.ts      # 宠物状态、配置、消息
├── composables/         # 可组合逻辑
│   ├── useWebSocket.ts  # WebSocket 客户端
│   ├── useConfig.ts     # 配置管理
│   ├── useLive2D.ts     # Live2D 控制
│   └── useVoice.ts      # 语音唤醒
├── components/          # 组件
│   ├── GalgameScene.vue # 主场景（背景+角色+文本框）
│   ├── Live2DCanvas.vue # Live2D 画布
│   ├── TextBox.vue      # VN 风格文字框
│   ├── MenuOverlay.vue  # 右上角菜单
│   ├── SettingsModal.vue# 设置窗口
│   └── LoadingScreen.vue# 加载页
├── views/               # 页面
│   ├── HomeView.vue     # 首页
│   └── SettingsView.vue # 设置页
├── types/               # 类型定义
├── lib/                 # 外部库（手动放置）
└── assets/              # 资源
    ├── backgrounds/     # 场景背景图
    └── styles/          # 样式
```

## WebSocket 协议

与桌面版 `qwenpaw_pet-app` 完全兼容。

**发送：**
```json
{"type": "text", "content": "你好"}
```

**接收（流式）：**
```json
{"type": "stream_delta", "text": "你"}
{"type": "stream_end", "text": "好"}
```

**配置 (`localStorage`)：**
```json
{
  "url": "ws://localhost:8765",
  "token": "",
  "streaming": true,
  "wake_word": "你好",
  "silence_timeout": 3,
  "voice_enabled": true
}
```

## License

MIT
