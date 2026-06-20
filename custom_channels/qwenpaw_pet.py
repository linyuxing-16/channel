# -*- coding: utf-8 -*-
# pylint: disable=too-many-statements,too-many-branches,too-many-return-statements
# pylint: disable=unused-argument
"""Qwenpaw Pet 渠道。

对外暴露 WebSocket 服务器，供外部客户端与 AI 通信。
客户端通过 ``Authorization: Bearer <token>`` 请求头进行鉴权，
发送文本消息，并通过同一 WebSocket 连接接收 AI 回复。
同时支持流式模式（逐 token 推送）和非流式模式（一次性返回完整消息）。

使用示例
--------
.. code-block:: python

    # 服务端（自动注册在 custom_channels/ 目录下）
    class QwenpawPetChannel(BaseChannel):
        channel = "qwenpaw-pet"
        ...

    # 客户端 (JavaScript)
    const ws = new WebSocket("ws://host:8765?streaming=1");
    ws.send(JSON.stringify({type: "text", content: "Hello"}));
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "stream_delta") console.log(msg.text);
    };
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import websockets
import websockets.exceptions
from websockets.server import WebSocketServer

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    TextContent,
)

from qwenpaw.app.channels.base import (
    BaseChannel,
    OnReplySent,
    OutgoingContentPart,
    ProcessHandler,
)

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────────

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8765
_PING_INTERVAL = 30  # 心跳 ping 间隔（秒）
_PING_TIMEOUT = 60   # 无响应断开超时（秒）

# ── 数据类 ─────────────────────────────────────────────────────────────


@dataclass
class ConnectionInfo:
    """保存一个 WebSocket 客户端连接的状态。"""

    websocket: Any
    client_id: str
    streaming_enabled: bool
    last_pong: float = field(default_factory=time.monotonic)


# ── 渠道实现 ────────────────────────────────────────────────────────────


class QwenpawPetChannel(BaseChannel):
    """WebSocket 服务器渠道，用于 AI 通信。

    客户端通过 WebSocket 连接，使用 Bearer token 鉴权，
    发送文本消息，并接收 AI 回复。
    同时支持流式模式（通过 ``on_streaming_delta`` 逐 token 推送）
    和非流式模式（一次性返回完整消息）。
    """

    channel = "qwenpaw-pet"
    streaming_enabled: bool = True

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        token: str,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        bot_prefix: str = "",
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
        require_mention: bool = False,
        streaming_enabled: bool = True,
    ):
        super().__init__(
            process=process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            require_mention=require_mention,
            streaming_enabled=streaming_enabled,
        )
        self.enabled = enabled
        self._token = token
        self._host = host
        self._port = port
        self.bot_prefix = bot_prefix

        # WebSocket 服务器
        self._ws_server: Optional[WebSocketServer] = None
        self._connections: Dict[str, ConnectionInfo] = {}
        self._stop_event = asyncio.Event()

    # ═══════════════════════════════════════════════════════════════════
    # 工厂方法
    # ═══════════════════════════════════════════════════════════════════

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "QwenpawPetChannel":
        """从环境变量构建实例。

        环境变量：
            QWENPAW_PET_ENABLED  是否启用（默认 "1"）
            QWENPAW_PET_TOKEN    鉴权令牌（必填，无默认值）
            QWENPAW_PET_HOST     监听地址（默认 "0.0.0.0"）
            QWENPAW_PET_PORT     监听端口（默认 "8765"）
            QWENPAW_PET_BOT_PREFIX 机器人前缀（默认 ""）
        """
        return cls(
            process=process,
            enabled=os.getenv("QWENPAW_PET_ENABLED", "1") == "1",
            token=os.getenv("QWENPAW_PET_TOKEN", ""),
            host=os.getenv("QWENPAW_PET_HOST", _DEFAULT_HOST),
            port=int(os.getenv("QWENPAW_PET_PORT", str(_DEFAULT_PORT))),
            bot_prefix=os.getenv("QWENPAW_PET_BOT_PREFIX", ""),
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Any,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
    ) -> "QwenpawPetChannel":
        """从配置对象构建实例。"""
        return cls(
            process=process,
            enabled=getattr(config, "enabled", True),
            token=getattr(config, "token", "")
            or os.getenv("QWENPAW_PET_TOKEN", ""),
            host=getattr(config, "host", _DEFAULT_HOST),
            port=int(getattr(config, "port", _DEFAULT_PORT)),
            bot_prefix=getattr(config, "bot_prefix", ""),
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
        )

    # ═══════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════

    async def start(self) -> None:
        """启动 WebSocket 服务器。"""
        if not self.enabled:
            logger.info("QwenpawPetChannel is disabled")
            return
        if not self._token:
            logger.warning(
                "QWENPAW_PET_TOKEN is not set; "
                "all connections will be rejected",
            )

        self._stop_event.clear()
        self._ws_server = await websockets.serve(
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=_PING_INTERVAL,
            ping_timeout=_PING_TIMEOUT,
        )
        logger.info(
            "QwenpawPetChannel WebSocket server started on %s:%s",
            self._host,
            self._port,
        )

    async def stop(self) -> None:
        """停止 WebSocket 服务器并断开所有客户端连接。"""
        if not self.enabled or self._ws_server is None:
            return

        self._stop_event.set()

        # 关闭所有活跃连接
        for conn in list(self._connections.values()):
            try:
                await conn.websocket.close(1001, "Server shutting down")
            except Exception:
                pass
        self._connections.clear()

        # 关闭服务器
        self._ws_server.close()
        await self._ws_server.wait_closed()
        self._ws_server = None
        logger.info("QwenpawPetChannel WebSocket server stopped")

    # ═══════════════════════════════════════════════════════════════════
    # WebSocket 连接处理
    # ═══════════════════════════════════════════════════════════════════

    async def _handle_connection(self, websocket) -> None:
        """处理新的 WebSocket 连接 — 鉴权，然后消息循环。"""
        # ── 鉴权 ─────────────────────────────────────────────────────
        token = self._extract_bearer_token(websocket)
        if not token or token != self._token:
            await websocket.close(4001, "Unauthorized")
            return

        # ── 流式偏好 ─────────────────────────────────────────────────
        streaming_enabled = self._detect_streaming_preference(websocket)

        # ── 注册连接 ─────────────────────────────────────────────────
        client_id = str(uuid.uuid4())
        conn = ConnectionInfo(
            websocket=websocket,
            client_id=client_id,
            streaming_enabled=streaming_enabled,
        )
        self._connections[client_id] = conn

        logger.info(
            "QwenpawPet client connected: %s (streaming=%s)",
            client_id[:8],
            streaming_enabled,
        )

        try:
            # 向客户端发送握手确认
            await self._send_json(websocket, {
                "type": "connected",
                "client_id": client_id,
                "streaming": streaming_enabled,
            })

            # ── 消息循环 ─────────────────────────────────────────────
            async for raw_message in websocket:
                if self._stop_event.is_set():
                    break
                try:
                    await self._handle_raw_message(
                        websocket,
                        client_id,
                        raw_message,
                    )
                except Exception as exc:
                    logger.exception(
                        "Error handling message from %s: %s",
                        client_id[:8],
                        exc,
                    )
                    await self._send_json(websocket, {
                        "type": "error",
                        "text": f"Message processing error: {exc}",
                    })

        except websockets.exceptions.ConnectionClosed:
            logger.debug("Client %s disconnected", client_id[:8])
        except Exception as exc:
            logger.exception(
                "WebSocket error for %s: %s",
                client_id[:8],
                exc,
            )
        finally:
            self._connections.pop(client_id, None)
            logger.info(
                "QwenpawPet client disconnected: %s",
                client_id[:8],
            )

    # ── 鉴权辅助方法 ─────────────────────────────────────────────────

    @staticmethod
    def _extract_bearer_token(websocket) -> str:
        """从请求头中提取 ``Authorization: Bearer <token>``。"""
        headers = websocket.request_headers
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):]
        return ""

    @staticmethod
    def _detect_streaming_preference(websocket) -> bool:
        """检测客户端是否请求了流式模式。

        检查 ``X-Streaming-Enabled`` 请求头。
        """
        headers = websocket.request_headers
        streaming_val = headers.get("X-Streaming-Enabled", "0")
        return streaming_val.lower() in ("1", "true", "yes")

    # ── 消息处理 ─────────────────────────────────────────────────────

    async def _handle_raw_message(
        self,
        websocket,
        client_id: str,
        raw_message: Any,
    ) -> None:
        """解析并入队一条原始 WebSocket 消息。"""
        # 将 bytes 解码为字符串
        text = (
            raw_message.decode("utf-8")
            if isinstance(raw_message, bytes)
            else str(raw_message)
        )

        # 解析 JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            await self._send_json(websocket, {
                "type": "error",
                "text": "Invalid JSON",
            })
            return

        # 校验消息类型
        msg_type = data.get("type", "text")
        if msg_type not in ("text", "message"):
            await self._send_json(websocket, {
                "type": "error",
                "text": f"Unsupported message type: {msg_type}",
            })
            return

        # 提取内容
        content = data.get("content", "") or data.get("text", "")
        if not content or not content.strip():
            await self._send_json(websocket, {
                "type": "error",
                "text": "Empty message content",
            })
            return

        # 确定会话 ID
        session_id = data.get(
            "session_id",
        ) or f"{self.channel}:{client_id}"

        # 构建给 manager 队列的原生 payload
        conn = self._connections.get(client_id)
        payload = {
            "channel_id": self.channel,
            "sender_id": client_id,
            "acl_sender_id": client_id,
            "content_parts": [
                TextContent(type=ContentType.TEXT, text=content.strip()),
            ],
            "meta": {
                "client_id": client_id,
                "session_id": session_id,
                "streaming_enabled": conn.streaming_enabled
                if conn
                else False,
            },
        }

        if self._enqueue is not None:
            self._enqueue(payload)
        else:
            logger.error("_enqueue not set; dropping message from %s", client_id[:8])
            await self._send_json(websocket, {
                "type": "error",
                "text": "Channel not ready — message dropped",
            })

    # ═══════════════════════════════════════════════════════════════════
    # 原生 payload → AgentRequest
    # ═══════════════════════════════════════════════════════════════════

    def build_agent_request_from_native(self, native_payload: Any) -> Any:
        """将 WebSocket 原生 payload 字典转换为 AgentRequest。

        payload 字典应包含:
            channel_id, sender_id, content_parts, meta
        """
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        content_parts = payload.get("content_parts") or []
        meta = dict(payload.get("meta") or {})

        session_id = self.resolve_session_id(sender_id, meta)

        request = self.build_agent_request_from_user_content(
            channel_id=channel_id,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        # 附加 channel_meta 供发送路径使用
        setattr(request, "channel_meta", meta)
        return request

    # ═══════════════════════════════════════════════════════════════════
    # 会话 ID 解析
    # ═══════════════════════════════════════════════════════════════════

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """解析会话标识符。

        如果 *channel_meta* 中包含客户端提供的显式 ``session_id``，
        则使用它；否则回退为 ``qwenpaw-pet:<sender_id>``。
        """
        if channel_meta and channel_meta.get("session_id"):
            return channel_meta["session_id"]
        return f"{self.channel}:{sender_id}"

    # ═══════════════════════════════════════════════════════════════════
    # 发送（基类在回复就绪时调用）
    # ═══════════════════════════════════════════════════════════════════

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """向 WebSocket 客户端发送一条文本消息。

        参数:
            to_handle: 目标 WebSocket 连接的 ``client_id``。
            text: 要发送的文本内容。
            meta: 可选元数据（``client_id``、``session_id`` 等）。
        """
        if not self.enabled:
            return

        meta = meta or {}
        client_id = meta.get("client_id", to_handle)
        conn = self._connections.get(client_id)
        if conn is None:
            logger.debug(
                "Cannot send: client %s not connected",
                client_id[:8] if client_id else "?",
            )
            return

        session_id = meta.get("session_id", "")
        try:
            await self._send_json(conn.websocket, {
                "type": "message",
                "text": text,
                "session_id": session_id,
            })
        except websockets.exceptions.ConnectionClosed:
            logger.debug(
                "Client %s disconnected during send",
                client_id[:8],
            )
            self._connections.pop(client_id, None)

    async def send_content_parts(
        self,
        to_handle: str,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将内容部件作为单条消息发送给 WebSocket 客户端。

        将 text/refusal 部件合并为一条文本，附加媒体 URL 作为内联占位符，
        然后通过 ``send()`` 发送。
        这是 ``on_event_message_completed`` 使用的发送路径（非 tracker / 回退路径）。
        """
        if not parts:
            return

        # 将各部件合并为一条文本（与基类相同逻辑）
        text_parts: List[str] = []
        for p in parts:
            t = getattr(p, "type", None)
            if t == ContentType.TEXT and getattr(p, "text", None):
                text_parts.append(p.text)
            elif t == ContentType.REFUSAL and getattr(p, "refusal", None):
                text_parts.append(p.refusal)
            elif t in (
                ContentType.IMAGE,
                ContentType.VIDEO,
                ContentType.AUDIO,
                ContentType.FILE,
            ):
                url = (
                    getattr(p, "image_url", None)
                    or getattr(p, "video_url", None)
                    or getattr(p, "file_url", None)
                    or getattr(p, "file_id", None)
                    or getattr(p, "data", None)
                    or ""
                )
                if url:
                    text_parts.append(f"[{t}: {url}]")

        body = "\n".join(text_parts) if text_parts else ""
        meta = meta or {}
        prefix = meta.get("bot_prefix", self.bot_prefix) or ""
        if prefix and body:
            body = prefix + "  " + body

        if body.strip():
            await self.send(to_handle, body.strip(), meta)

    # ═══════════════════════════════════════════════════════════════════
    # 流式钩子
    # ═══════════════════════════════════════════════════════════════════

    async def on_streaming_start(
        self,
        request: Any,
        to_handle: str,
        event: Any,
        send_meta: Dict[str, Any],
        stream_type: str,
        accumulated_text: str = "",
    ) -> None:
        """向流式客户端发送 ``stream_start`` 事件。"""
        conn = self._connections.get(to_handle)
        if conn is None or not conn.streaming_enabled:
            return

        session_id = getattr(request, "session_id", "") or send_meta.get(
            "session_id",
            "",
        )
        await self._safe_send(conn, {
            "type": "stream_start",
            "stream_type": stream_type,
            "session_id": session_id,
        })

    async def on_streaming_delta(
        self,
        request: Any,
        to_handle: str,
        event: Any,
        send_meta: Dict[str, Any],
        stream_type: str,
        accumulated_text: str = "",
    ) -> None:
        """向流式客户端发送 ``stream_delta`` 事件。"""
        conn = self._connections.get(to_handle)
        if conn is None or not conn.streaming_enabled:
            return

        session_id = getattr(request, "session_id", "") or send_meta.get(
            "session_id",
            "",
        )
        await self._safe_send(conn, {
            "type": "stream_delta",
            "text": accumulated_text,
            "stream_type": stream_type,
            "session_id": session_id,
        })

    async def on_streaming_end(
        self,
        request: Any,
        to_handle: str,
        event: Any,
        send_meta: Dict[str, Any],
        stream_type: str,
        accumulated_text: str = "",
    ) -> None:
        """向 **所有** 已连接客户端发送 ``stream_end`` 事件。

        非流式客户端在此处收到完整回复（作为单次 ``stream_end`` 事件），
        而流式客户端在经过一系列 ``stream_delta`` 事件后收到最终 delta。
        """
        conn = self._connections.get(to_handle)
        if conn is None:
            return

        session_id = getattr(request, "session_id", "") or send_meta.get(
            "session_id",
            "",
        )
        await self._safe_send(conn, {
            "type": "stream_end",
            "text": accumulated_text,
            "stream_type": stream_type,
            "session_id": session_id,
        })

    async def on_event_message_completed(
        self,
        request: Any,
        to_handle: str,
        event: Any,
        send_meta: Dict[str, Any],
    ) -> None:
        """已完成消息的回退发送路径。

        在 tracker 路径 (``_stream_with_tracker``) 中，
        completed 消息通过 ``on_streaming_end`` 发送，**不会**调用此方法。
        在非 tracker 路径 (``_run_process_loop``) 中，
        这是唯一的发送路径 — 转发到基类的 ``send_message_content``，
        它会调用 ``send_content_parts``。
        """
        await super().on_event_message_completed(
            request,
            to_handle,
            event,
            send_meta,
        )

    # ═══════════════════════════════════════════════════════════════════
    # 内部辅助方法
    # ═══════════════════════════════════════════════════════════════════

    async def _send_json(self, websocket, data: dict) -> None:
        """将 *data* 序列化为 JSON 并通过 *websocket* 发送。"""
        text = json.dumps(data, ensure_ascii=False)
        await websocket.send(text)

    async def _safe_send(self, conn: ConnectionInfo, data: dict) -> None:
        """发送 JSON 数据，优雅处理已关闭的连接。"""
        try:
            await self._send_json(conn.websocket, data)
        except websockets.exceptions.ConnectionClosed:
            # 移除已断开的连接
            self._connections.pop(conn.client_id, None)

    async def health_check(self) -> Dict[str, Any]:
        """报告渠道健康状态。"""
        if not self.enabled:
            return {
                "channel": self.channel,
                "status": "disabled",
                "detail": "QwenpawPetChannel is disabled.",
            }
        client_count = len(self._connections)
        return {
            "channel": self.channel,
            "status": "healthy",
            "detail": (
                f"WebSocket server running on {self._host}:{self._port}. "
                f"Active connections: {client_count}."
            ),
            "clients": client_count,
        }
