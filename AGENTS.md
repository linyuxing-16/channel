# Qwenpaw Pet Channel — 项目指南

## 项目概览

本项目包含两个部分：

| 组件 | 路径 | 说明 |
|------|------|------|
| **WebSocket 服务端（渠道）⚠️ 废弃** | `custom_channels/qwenpaw_pet.py` | 基于 `agentscope_runtime` 框架，已废弃，改用 Hermes 插件 |
| **Hermes 平台适配器 ✅ 推荐** | `.hermes/plugins/qwenpaw_pet/` | Hermes Agent 项目级插件，功能完全替代旧版通道 |
| **桌面宠物客户端** | `qwenpaw_pet-app/` | 基于 tkinter 的桌面宠物应用，通过 WebSocket 连接服务端 |
| **测试服务器** | `test_server.py` | 独立 WebSocket 回声测试服务器，不依赖框架 |

---

## 桌面宠物客户端 (`qwenpaw_pet-app/`)

### 启动方式

```bash
cd qwenpaw_pet-app
python main.py
```

### 依赖

- `Pillow` — 图片加载
- `websockets` — WebSocket 客户端

### 配置

编辑 `qwenpaw_pet-app/config.json`：

```json
{
    "url": "ws://localhost:8765",
    "token": "",
    "streaming": true
}
```

### 架构

```
main.py                          # 入口：组装各组件，启动事件循环
├── config.py                    # 加载 config.json → url, token, stream
├── websocket_pet.py             # QwenpawPetClient (WebSocket 客户端)
├── windows.py                   # tkinter UI 组件
│   ├── PetWindow                # 透明无边框桌面宠物主窗口
│   ├── DialogController         # 控制面板（4 个按钮）
│   ├── SettingController        # 设置窗口（修改 url/token/streaming）
│   └── ChatInputController      # 输入/显示对话框
└── images/                      # 宠物状态图片（需自行添加）
    ├── 沉默.png
    ├── 思考.png
    └── 说话.png

# 项目根目录
test_server.py                   # 独立 WebSocket 回声测试服务器
```

### 状态流转

- **沉默** (`沉默.png`) — 默认状态，空闲等待
- **思考** (`思考.png`) — 消息发送中
- **说话** (`说话.png`) — 收到 AI 回复

### 关键类

| 类 | 文件 | 职责 |
|---|------|------|
| `QwenpawPetClient` | `websocket_pet.py` | WebSocket 客户端，连接/发送/接收消息，支持流式回调 |
| `PetWindow` | `windows.py` | 透明无边框桌面宠物窗口，点击切换 DialogController |
| `DialogController` | `windows.py` | 控制面板，含设置/打开对话框/关闭对话框/退出 4 个按钮 |
| `SettingController` | `windows.py` | 设置窗口，修改 url/token/streaming 并保存到 config.json |
| `ChatInputController` | `windows.py` | 文本输入/显示双模式对话框 |

### 通信流程

1. 启动 → 创建事件循环（守护线程）→ 连接 WebSocket → 开始消费消息队列
2. `send_message_sync()` → 切换为"思考"状态 → 通过 WebSocket 发送文本
3. 服务端回复 → `consume_messages()` → 切换为"说话"状态并显示文本
4. 流式结束（`is_end=True`）→ 切换回"沉默"状态

---

## WebSocket 服务端 (`custom_channels/qwenpaw_pet.py`) — ⚠️ 已废弃

> **此版本基于 `agentscope_runtime` 框架，已被废弃。**
> 请改用本项目的 [Hermes 项目级插件](.hermes/plugins/qwenpaw_pet/)，
> 它作为 Hermes 插件运行，无需 `agentscope_runtime` 框架。
> `qwenpaw_pet-app` 客户端协议完全兼容，无需任何修改。

### 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QWENPAW_PET_ENABLED` | `1` | 是否启用 |
| `QWENPAW_PET_TOKEN` | (必填) | Bearer 鉴权令牌 |
| `QWENPAW_PET_HOST` | `0.0.0.0` | 监听地址 |
| `QWENPAW_PET_PORT` | `8765` | 监听端口 |
| `QWENPAW_PET_BOT_PREFIX` | `""` | 机器人前缀 |

### WebSocket 协议

**客户端 → 服务端：**

```json
// 文本消息
{"type": "text", "content": "你好"}

// 多模态消息
{
    "type": "text",
    "content": [
        {"type": "text", "text": "这是什么？"},
        {"type": "image", "data": "<base64>", "format": "png"}
    ],
    "session_id": "optional-session-id"
}
```

**服务端 → 客户端（流式模式）：**

```json
{"type": "stream_start"}
{"type": "stream_delta", "text": "你"}
{"type": "stream_delta", "text": "好"}
{"type": "stream_end",   "text": "好"}
```

**服务端 → 客户端（非流式）：**

```json
{"type": "message", "text": "你好！有什么可以帮你的？"}
```

**握手：**

```json
{"type": "connected", "client_id": "uuid", "streaming": true}
```

### 鉴权

客户端在 WebSocket 请求头中携带：
```
Authorization: Bearer <token>
X-Streaming-Enabled: 1
```

### 通道注册

该渠道继承 `BaseChannel`，通过 `from_env()` 或 `from_config()` 工厂方法构建，自动被 `agentscope_runtime` 框架发现并注册。

---

## 测试服务器 (`test_server.py`)

项目根目录下的 `test_server.py` 是一个**完全独立**的 WebSocket 回声测试服务器，不依赖 `agentscope_runtime` 框架，用于单独测试桌面客户端。

```bash
# 默认 0.0.0.0:8765，无鉴权
python test_server.py

# 自定义端口和 Bearer 鉴权
python test_server.py --port 8888 --token my-secret
```

关键类 `QwenpawPetTestServer`：
- `run()` — 启动服务器（`asyncio.Future()` 阻塞直到被取消）
- `_handle_connection()` — 鉴权 → 握手 → 消息循环
- `_send_streaming_reply()` — 逐字符模拟流式（20ms 间隔）

**重要**：该文件与 `custom_channels/qwenpaw_pet.py` 使用相同的 WebSocket 协议，但完全是独立的实现。

---

## 依赖管理

项目当前**没有** `requirements.txt` 或 `pyproject.toml`。手动安装依赖：

```bash
pip install websockets Pillow
```

| 依赖 | 用途 |
|------|------|
| `websockets` | WebSocket 客户端 (`qwenpaw_pet-app`) 和服务端 (`test_server.py`) |
| `Pillow` | 桌面宠物状态图片加载 (`qwenpaw_pet-app`) |

---

## 项目配置

### `.gitignore`

```gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
*.egg-info/
dist/
build/
.egg/
.venv/
```

### `config.json` 字段

文件位置：`qwenpaw_pet-app/config.json`

```json
{
    "url": "ws://localhost:8765",
    "token": "",
    "streaming": true
}
```

**⚠️ 已知陷阱：字段名不统一**
- `config.json` 使用键 `"streaming"`
- `config.py` 读取时使用 `_config.get("stream", True)` — **读取的是 `"stream"`，不是 `"streaming"`**
- `SettingController._save_config()` 写入的是 `"streaming"`
- **后果**：通过设置界面修改后保存的值，`config.py` 读取不到（始终返回默认值 `True`）
- **修复建议**：将 `config.py` 中的 `"stream"` 改为 `"streaming"`，或将 `SettingController` 中的写入键统一

---

## 常见陷阱

1. **`images/` 目录为空** — 需要放入 `沉默.png`、`思考.png`、`说话.png` 三张图片，否则会用 1x1 占位图
2. **`config.json` 字段名不统一** — `config.py` 读 `"stream"`，`SettingController` 写 `"streaming"`（见上文）
3. **事件循环** — `main.py` 使用独立事件循环在守护线程中运行，tkinter 主循环在主线程阻塞
4. **线程安全** — UI 更新需通过 `root.after(0, ...)` 调度到主线程执行
5. **缺少依赖管理文件** — 无 `requirements.txt`，依赖需手动安装
6. **`test_server.py` 不依赖框架** — 它与 `custom_channels/qwenpaw_pet.py` 使用相同的协议但互不依赖，测试时注意选择正确的服务器
