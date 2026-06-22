# Qwenpaw Pet Channel

桌面宠物应用 + WebSocket AI 通信渠道。

## 项目结构

| 组件 | 路径 | 说明 |
|------|------|------|
| **桌面宠物客户端** | `qwenpaw_pet-app/` | tkinter 桌面宠物，通过 WebSocket 连接 AI |
| **WebSocket 服务端** | `custom_channels/qwenpaw_pet.py` | AI 通信渠道（agentscope_runtime 框架） |

详见 [AGENTS.md](./AGENTS.md) 获取完整的开发指南。