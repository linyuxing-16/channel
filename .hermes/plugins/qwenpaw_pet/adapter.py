"""
Qwenpaw Pet Platform Adapter for Hermes Agent.

项目级（project-level）Hermes 插件，启动 WebSocket 服务器供
``qwenpaw_pet-app`` 桌面宠物客户端连接，将消息透传给 Hermes AI Agent。

协议与原始 ``custom_channels/qwenpaw_pet.py`` 完全兼容，
``qwenpaw_pet-app`` 客户端无需任何修改。

配置方式
--------

环境变量（推荐，零配置启动）::

    set QWENPAW_PET_TOKEN=your-secret-token
    set HERMES_ENABLE_PROJECT_PLUGINS=1
    hermes gateway start

``config.yaml``（可选）::

    gateway:
      platforms:
        qwenpaw_pet:
          enabled: true
          extra:
            token: "your-secret-token"
            host: "0.0.0.0"
            port: 8765
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import websockets
import websockets.exceptions
from websockets.server import WebSocketServer

from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)
from gateway.config import Platform, PlatformConfig
from gateway.session import SessionSource

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────────

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8765
_PING_INTERVAL = 30
_PING_TIMEOUT = 60

# 流式发送时 stream_delta 的最小间隔（秒），避免高频推送
_STREAM_DELTA_MIN_INTERVAL = 0.02


# ── 连接信息 ────────────────────────────────────────────────────────────


class _ClientConnection:
    """保存一个 WebSocket 客户端连接的状态。"""

    def __init__(self, websocket, client_id: str, streaming_enabled: bool) -> None:
        self.websocket = websocket
        self.client_id = client_id
        self.streaming_enabled = streaming_enabled
        self.stream_active = False  # 当前是否处于流式发送中


# ── 适配器 ──────────────────────────────────────────────────────────────


class QwenpawPetAdapter(BasePlatformAdapter):
    """WebSocket 服务器适配器，用于 Qwenpaw Pet 桌面宠物客户端。

    启动一个 WebSocket 服务器，qwenpaw_pet-app 客户端连接后可以
    通过 Hermes Agent 进行 AI 对话。支持流式和非流式模式。

    WebSocket 协议（与 custom_channels/qwenpaw_pet.py 兼容）:
        客户端 → 服务端:  {"type": "text", "content": "你好"}
        服务端 → 客户端:  {"type": "connected", "client_id": "...", "streaming": true}
        流式响应:         stream_start → stream_delta × N → stream_end
        非流式响应:       {"type": "message", "text": "..."}
    """

    def __init__(self, config: PlatformConfig) -> None:
        # Platform("qwenpaw_pet") 通过 Platform._missing_ 动态创建枚举成员
        super().__init__(config, Platform("qwenpaw_pet"))

        extra = config.extra or {}

        self._token: str = extra.get("token", "")
        self._host: str = extra.get("host", _DEFAULT_HOST)
        self._port: int = int(extra.get("port", _DEFAULT_PORT))

        # WebSocket 服务器实例
        self._ws_server: Optional[WebSocketServer] = None

        # 已连接的客户端: client_id -> _ClientConnection
        self._clients: Dict[str, _ClientConnection] = {}
        # websocket 对象 -> _ClientConnection 反向查找
        self._conn_by_ws: Dict[Any, _ClientConnection] = {}

        # 流式状态跟踪: chat_id -> bool
        self._stream_active: Dict[str, bool] = {}

    # ── 属性 ─────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Qwenpaw Pet"

    @property
    def is_connected(self) -> bool:
        return self._ws_server is not None and self._running

    # ── 生命周期 ─────────────────────────────────────────────────────

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """启动 WebSocket 服务器。"""
        try:
            self._ws_server = await websockets.serve(
                self._handle_connection,
                self._host,
                self._port,
                ping_interval=_PING_INTERVAL,
                ping_timeout=_PING_TIMEOUT,
            )
            self._mark_connected()
            host_display = self._host if self._host != "0.0.0.0" else "localhost"
            logger.info(
                "[Qwenpaw Pet] WebSocket server started on ws://%s:%s",
                host_display, self._port,
            )
            return True
        except Exception as exc:
            logger.error("[Qwenpaw Pet] Failed to start server: %s", exc)
            return False

    async def disconnect(self) -> None:
        """关闭 WebSocket 服务器和所有客户端连接。"""
        for conn in list(self._clients.values()):
            try:
                await conn.websocket.close(1001, "Server shutting down")
            except Exception:
                pass
        self._clients.clear()
        self._conn_by_ws.clear()
        self._stream_active.clear()

        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

        self._mark_disconnected()
        logger.info("[Qwenpaw Pet] Server stopped")

    # ── 发送消息 ─────────────────────────────────────────────────────

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """向指定客户端发送消息。

        由 GatewayStreamConsumer 驱动，支持流式渐进式发送。
        """
        conn = self._clients.get(chat_id)
        if conn is None:
            return SendResult(success=False, error=f"Client {chat_id} not connected")

        meta = metadata or {}
        expect_edits = meta.get("expect_edits", False)

        try:
            if conn.streaming_enabled:
                if expect_edits:
                    # 流式预览模式 — 由 GatewayStreamConsumer 驱动
                    if not conn.stream_active:
                        await self._send_json(conn.websocket, {"type": "stream_start"})
                        conn.stream_active = True
                        await asyncio.sleep(_STREAM_DELTA_MIN_INTERVAL)

                    await self._send_json(conn.websocket, {
                        "type": "stream_delta",
                        "text": content,
                    })
                else:
                    # 最终/非流式发送
                    if conn.stream_active:
                        await self._send_json(conn.websocket, {
                            "type": "stream_end",
                            "text": content,
                        })
                        conn.stream_active = False
                    else:
                        await self._send_json(conn.websocket, {
                            "type": "message",
                            "text": content,
                        })
            else:
                # 客户端请求非流式模式
                await self._send_json(conn.websocket, {
                    "type": "message",
                    "text": content,
                })

            return SendResult(success=True, message_id=str(int(time.time() * 1000)))
        except Exception as exc:
            logger.error("[Qwenpaw Pet] Send failed for %s: %s", chat_id, exc)
            return SendResult(success=False, error=str(exc))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """发送"正在输入"指示。对于流式模式，发 stream_start 信号。"""
        conn = self._clients.get(chat_id)
        if conn is None or not conn.streaming_enabled:
            return
        try:
            if not conn.stream_active:
                await self._send_json(conn.websocket, {"type": "stream_start"})
                conn.stream_active = True
        except Exception:
            pass

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        metadata=None,
    ) -> SendResult:
        """发送图片消息。"""
        conn = self._clients.get(chat_id)
        if conn is None:
            return SendResult(success=False, error=f"Client {chat_id} not connected")

        try:
            content: list[dict] = []
            if caption:
                content.append({"type": "text", "text": caption})
            content.append({"type": "image", "data": image_url, "format": "url"})

            await self._send_json(conn.websocket, {
                "type": "text",
                "content": content,
            })
            return SendResult(success=True, message_id=str(int(time.time() * 1000)))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """获取客户端信息。"""
        conn = self._clients.get(chat_id)
        if conn is None:
            return {"name": chat_id, "type": "dm", "chat_id": chat_id}
        return {
            "name": conn.client_id[:8],
            "type": "dm",
            "chat_id": chat_id,
        }

    # ── WebSocket 连接处理 ──────────────────────────────────────────

    async def _handle_connection(self, websocket) -> None:
        """处理新的 WebSocket 客户端连接。"""
        req_headers = websocket.request.headers

        # ── 鉴权 ─────────────────────────────────────────────────
        if self._token:
            token = self._extract_bearer_token(req_headers)
            if not token or token != self._token:
                await websocket.close(4001, "Unauthorized")
                return

        # ── 流式偏好 ─────────────────────────────────────────────
        streaming_enabled = self._detect_streaming_preference(req_headers)
        client_id = str(uuid.uuid4())

        # ── 注册连接 ─────────────────────────────────────────────
        conn = _ClientConnection(websocket, client_id, streaming_enabled)
        self._clients[client_id] = conn
        self._conn_by_ws[websocket] = conn

        logger.info(
            "[Qwenpaw Pet] Client connected: %s (streaming=%s)",
            client_id[:8], streaming_enabled,
        )

        try:
            # 发送握手
            await self._send_json(websocket, {
                "type": "connected",
                "client_id": client_id,
                "streaming": streaming_enabled,
            })

            # 消息循环
            async for raw_message in websocket:
                await self._handle_raw_message(websocket, client_id, raw_message)

        except websockets.exceptions.ConnectionClosed:
            logger.debug("[Qwenpaw Pet] Client %s disconnected", client_id[:8])
        except Exception as exc:
            logger.exception(
                "[Qwenpaw Pet] Error handling client %s: %s", client_id[:8], exc,
            )
        finally:
            self._clients.pop(client_id, None)
            self._conn_by_ws.pop(websocket, None)
            self._stream_active.pop(client_id, None)
            logger.info("[Qwenpaw Pet] Client gone: %s", client_id[:8])

    async def _handle_raw_message(
        self,
        websocket,
        client_id: str,
        raw_message: bytes | str,
    ) -> None:
        """处理一条客户端原始消息。"""
        text = (
            raw_message.decode("utf-8")
            if isinstance(raw_message, bytes)
            else str(raw_message)
        )

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            await self._send_json(websocket, {"type": "error", "text": "Invalid JSON"})
            return

        msg_type = data.get("type", "")
        if msg_type not in ("text", "message"):
            await self._send_json(websocket, {
                "type": "error",
                "text": f"Unsupported message type: {msg_type}",
            })
            return

        content = data.get("content", "") or data.get("text", "")
        session_id = data.get("session_id")

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            reply_text = " ".join(text_parts) if text_parts else "(multimodal message)"
        else:
            reply_text = str(content).strip()

        if not reply_text:
            await self._send_json(websocket, {
                "type": "error",
                "text": "Empty message content",
            })
            return

        await self._dispatch_message(
            text=reply_text,
            chat_id=client_id,
            user_id=client_id,
            user_name=f"pet-{client_id[:8]}",
            session_id=session_id,
        )

    async def _dispatch_message(
        self,
        text: str,
        chat_id: str,
        user_id: str,
        user_name: str,
        session_id: Optional[str] = None,
    ) -> None:
        """构建 MessageEvent 并交给基类的消息处理器。"""
        if not self._message_handler:
            return

        source = self.build_source(
            chat_id=chat_id,
            chat_name=user_name,
            chat_type="dm",
            user_id=user_id,
            user_name=user_name,
            thread_id=session_id,
        )

        event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            message_id=str(int(time.time() * 1000)),
            timestamp=__import__("datetime").datetime.now(),
        )

        await self.handle_message(event)

    # ── 辅助方法 ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_bearer_token(headers: Any) -> str:
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):]
        return ""

    @staticmethod
    def _detect_streaming_preference(headers: Any) -> bool:
        sv = headers.get("X-Streaming-Enabled", "1")
        return sv.lower() in ("1", "true", "yes")

    @staticmethod
    async def _send_json(websocket, data: dict) -> None:
        text = json.dumps(data, ensure_ascii=False)
        await websocket.send(text)


# ── 插件注册辅助函数 ────────────────────────────────────────────────────


def check_requirements() -> bool:
    try:
        import websockets  # noqa: F401
        return True
    except ImportError:
        return False


def validate_config(config: PlatformConfig) -> bool:
    extra = config.extra or {}
    token = extra.get("token", "") or os.getenv("QWENPAW_PET_TOKEN", "")
    return bool(token)


def is_connected(config: PlatformConfig) -> bool:
    return False  # GatewayRunner 管理实际状态


def _env_enablement() -> Optional[dict]:
    """从环境变量构建 PlatformConfig.extra 和 home_channel。"""
    token = os.getenv("QWENPAW_PET_TOKEN", "")
    if not token:
        return None

    extra: dict = {"token": token}
    host = os.getenv("QWENPAW_PET_HOST")
    if host:
        extra["host"] = host
    port = os.getenv("QWENPAW_PET_PORT")
    if port:
        extra["port"] = port

    home_channel: Optional[str] = os.getenv("QWENPAW_PET_HOME_CHANNEL")

    result: dict = {"extra": extra}
    if home_channel:
        result["home_channel"] = home_channel
    return result


async def _standalone_send(params: dict) -> dict:
    return {"success": False, "error": "Standalone send not supported yet"}


# ── 插件注册入口 ────────────────────────────────────────────────────────


def register(ctx):
    """Plugin entry point: called by the Hermes plugin system."""
    ctx.register_platform(
        name="qwenpaw_pet",
        label="Qwenpaw Pet",
        adapter_factory=lambda cfg: QwenpawPetAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["QWENPAW_PET_TOKEN"],
        install_hint="Install with: pip install websockets",
        setup_fn=None,
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="QWENPAW_PET_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        allowed_users_env="QWENPAW_PET_ALLOWED_USERS",
        allow_all_env="QWENPAW_PET_ALLOW_ALL_USERS",
        max_message_length=0,
        emoji="🦎",
        pii_safe=False,
        allow_update_command=True,
        platform_hint=(
            "You are chatting through a Qwenpaw Pet desktop companion. "
            "The user sees a transparent pet window on their desktop. "
            "Messages appear as speech bubbles. "
            "Supports streaming responses (shown incrementally). "
            "Keep responses concise — the desktop UI has limited space."
        ),
    )
