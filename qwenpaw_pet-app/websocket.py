"""
WebSocket 客户端，用于连接 custom_channels/qwenpaw_pet.py 的 WebSocket 服务器。

提供连接、发送消息(包括文本和base64编码的多模态消息)、接收回调等功能，支持流式和非流式消息处理。
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)


class QwenpawPetClient:
    """QwenpawPet WebSocket 客户端。

    连接到 QwenpawPet WebSocket 服务器，发送消息并通过回调函数接收回复。

    用法::

        async def on_message(content: str, is_end: bool) -> None:
            print(f"[{'END' if is_end else 'DELTA'}]: {content}")

        client = QwenpawPetClient(
            url="ws://localhost:8765",
            token="my-token",
            callback=on_message,
        )
        await client.connect()
        await client.send_message("你好")
        # ... 接收消息 ...
        await client.close()
    """

    def __init__(
        self,
        url: str,
        token: str,
        callback: Callable[[str, bool], None],
    ) -> None:
        """初始化客户端。

        Args:
            url: WebSocket 服务器地址，如 ``ws://host:8765``。
            token: Bearer token，用于鉴权。
            callback: 消息回调函数，接收两个参数：
                - ``content`` (str): 消息内容。
                - ``is_end`` (bool): 是否为最后一条消息。
                  流式模式下每条 delta 回调 ``is_end=False``，
                  最后一条回调 ``is_end=True``；
                  非流式模式下单次回调 ``is_end=True``。
            """
        self._url = url
        self._token = token
        self._callback = callback
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected: bool = False

    # ── 连接 ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """连接到 WebSocket 服务器。

        在请求头中附加 ``Authorization: Bearer <token>`` 进行鉴权。
        连接成功后等待握手消息 ``{"type": "connected"}``，
        然后进入消息接收循环。

        Raises:
            websockets.exceptions.WebSocketException: 连接失败时抛出。
        """
        extra_headers = {"Authorization": f"Bearer {self._token}"}
        self._ws = await websockets.connect(
            self._url,
            extra_headers=extra_headers,
        )
        self._connected = True

        # 等待握手消息
        raw = await self._ws.recv()
        handshake = json.loads(
            raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        )
        if handshake.get("type") != "connected":
            logger.warning(
                "Unexpected handshake message: %s", handshake.get("type"),
            )

        logger.info(
            "Connected to QwenpawPet server at %s (client_id=%s)",
            self._url,
            handshake.get("client_id", "?"),
        )

        # 进入消息接收循环
        await self._message_loop()

    async def _message_loop(self) -> None:
        """消息接收循环，根据消息类型调度回调。"""
        try:
            async for raw_message in self._ws:
                text = (
                    raw_message.decode("utf-8")
                    if isinstance(raw_message, bytes)
                    else str(raw_message)
                )
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON: %s", text[:200])
                    continue

                msg_type = data.get("type", "")

                if msg_type == "stream_delta":
                    # 流式 delta — 未结束
                    content = data.get("text", "")
                    self._callback(content, False)

                elif msg_type == "stream_end":
                    # 流式结束 — 最后一条
                    content = data.get("text", "")
                    self._callback(content, True)

                elif msg_type == "message":
                    # 非流式完整消息 — 一次性结束
                    content = data.get("text", "")
                    self._callback(content, True)

                elif msg_type == "error":
                    # 服务端错误
                    error_text = data.get("text", "Unknown error")
                    logger.error("Server error: %s", error_text)
                    raise RuntimeError(f"Server error: {error_text}")

                elif msg_type == "stream_start":
                    # 流式开始标记，忽略
                    pass

                elif msg_type == "connected":
                    # 重复握手，忽略
                    pass

                else:
                    logger.debug("Unhandled message type: %s", msg_type)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        finally:
            self._connected = False

    # ── 发送消息 ─────────────────────────────────────────────────────

    async def send_message(
        self,
        content: str | list[dict],
        session_id: Optional[str] = None,
    ) -> None:
        """发送消息到 WebSocket 服务器。

        支持纯文本和 base64 编码的多模态消息。

        Args:
            content: 消息内容。
                - 纯文本时传入 ``str``。
                - 多模态消息时传入 ``list[dict]``，每个 dict 包含:
                    - ``{"type": "text", "text": "..."}`` — 文本
                    - ``{"type": "image", "image_url": "...", "data": "...", "format": "png"}`` — 图片
                    - ``{"type": "file", "data": "...", "filename": "file.pdf"}`` — 文件
                    - ``{"type": "audio", "data": "...", "format": "wav"}`` — 音频
                    - ``{"type": "video", "video_url": "...", "data": "...", "format": "mp4"}`` — 视频
            session_id: 可选的会话 ID。

        Raises:
            RuntimeError: 客户端未连接时抛出。
        """
        if not self._connected or self._ws is None:
            raise RuntimeError("Client is not connected")

        payload: dict = {"type": "text", "content": content}
        if session_id is not None:
            payload["session_id"] = session_id

        await self._ws.send(json.dumps(payload, ensure_ascii=False))

    # ── 关闭连接 ─────────────────────────────────────────────────────

    async def close(self) -> None:
        """关闭 WebSocket 连接。"""
        self._connected = False
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
            logger.info("WebSocket connection closed")

    # ── 属性 ─────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        """是否已连接。"""
        return self._connected