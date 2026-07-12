# Qwenpaw Pet Channel

桌面宠物应用 + WebSocket AI 通信渠道。

## 项目结构

| 组件 | 路径 | 说明 |
|------|------|------|
| **桌面宠物客户端** | `qwenpaw_pet-app/` | tkinter 桌面宠物，通过 WebSocket 连接 AI |
| **WebSocket 服务端 ⚠️ 废弃** | `custom_channels/qwenpaw_pet.py` | AI 通信渠道（agentscope_runtime 框架，已废弃，改用 Hermes 插件） |
| **测试服务器** | `test_server.py` | 独立 WebSocket 回声服务器，用于测试客户端 |

详见 [AGENTS.md](./AGENTS.md) 获取完整的开发指南。

> 💡 **新方案**：Qwenpaw Pet 现已提供 [Hermes Agent 插件](.hermes/plugins/qwenpaw_pet/)，
> 作为 Hermes 项目级插件运行（需设置 `HERMES_ENABLE_PROJECT_PLUGINS=1`）。
> 配置环境变量 `QWENPAW_PET_TOKEN` 即可通过 Hermes 网关使用。
> 桌面客户端 `qwenpaw_pet-app` 无需任何修改。