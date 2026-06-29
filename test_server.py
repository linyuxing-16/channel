#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwenpaw Pet — WebSocket 测试服务端（回声模式）

完全独立于 agentscope_runtime 框架，用于测试 qwenpaw_pet-app 客户端。
将客户端发送的消息原样返回，支持流式和非流式两种模式。

用法:
    # 默认监听 0.0.0.0:8765，无鉴权
    python test_server.py

    # 自定义端口和 token
    python test_server.py --port 8888 --token my-secret

    # 查看帮助
    python test_server.py --help

协议（与 custom_channels/qwenpaw_pet.py 一致）:
    客户端 → 服务端:  {"type": "text", "content": "你好"}
    服务端 → 客户端:  {"type": "connected", "client_id": "...", "streaming": true}
    流式响应:         stream_start → stream_delta × N → stream_end
    非流式响应:       {"type": "message", "text": "..."}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from typing import Any

import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────────

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8765
_PING_INTERVAL = 30
_PING_TIMEOUT = 60

# ── 测试服务端 ──────────────────────────────────────────────────────────


class QwenpawPetTestServer:
    """Qwenpaw Pet WebSocket 测试服务端（回声模式）。

    将客户端发来的消息原样返回，用于客户端功能测试。
    支持流式和非流式两种模式，以及可选的 Bearer token 鉴权。

    用法:
        server = QwenpawPetTestServer(host="0.0.0.0", port=8765)
        asyncio.run(server.run())
    """

    def __init__(
        self,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        token: str = "",
    ) -> None:
        """初始化测试服务端。

        Args:
            host: 监听地址，默认 "0.0.0.0"。
            port: 监听端口，默认 8765。
            token: Bearer token。为空字符串时跳过鉴权。
        """
        self._host = host
        self._port = port
        self._token = token
        self._ws_server: Any | None = None

    # ── 生命周期 ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """启动服务器并持续运行，直到收到 SIGINT。"""
        self._ws_server = await websockets.serve(
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=_PING_INTERVAL,
            ping_timeout=_PING_TIMEOUT,
        )

        host_display = self._host if self._host != "0.0.0.0" else "localhost"
        token_info = " (token 验证已启用)" if self._token else " (无鉴权)"
        print(f"🦎 Qwenpaw Pet 测试服务端已启动")
        print(f"   地址: ws://{host_display}:{self._port}")
        print(f"   模式: 回声 (echo){token_info}")
        print(f"   按 Ctrl+C 停止服务器")
        print()

        try:
            await asyncio.Future()  # 运行直到被取消
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        """关闭服务器。"""
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None
            print("🦎 测试服务端已停止")

    # ── 连接处理 ─────────────────────────────────────────────────────

    async def _handle_connection(self, websocket) -> None:
        """处理新的 WebSocket 连接。"""
        # websockets v16: request headers 通过 websocket.request.headers 访问
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

        print(f"🔗 新客户端连接: {client_id[:8]} (streaming={streaming_enabled})")

        try:
            # 发送握手
            await self._send_json(websocket, {
                "type": "connected",
                "client_id": client_id,
                "streaming": streaming_enabled,
            })

            # 消息循环
            async for raw_message in websocket:
                await self._handle_message(
                    websocket, client_id, raw_message, streaming_enabled,
                )

        except websockets.exceptions.ConnectionClosed:
            logger.debug("客户端 %s 断开连接", client_id[:8])
        except Exception as exc:
            logger.exception("处理客户端 %s 时出错: %s", client_id[:8], exc)
        finally:
            print(f"🔌 客户端断开连接: {client_id[:8]}")

    # ── 消息处理 ─────────────────────────────────────────────────────

    async def _handle_message(
        self,
        websocket,
        client_id: str,
        raw_message: bytes | str,
        streaming_enabled: bool,
    ) -> None:
        """处理一条客户端消息，以回声模式回复。"""
        # 解码
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
        msg_type = data.get("type", "")
        if msg_type not in ("text", "message"):
            await self._send_json(websocket, {
                "type": "error",
                "text": f"Unsupported message type: {msg_type}",
            })
            return

        # 提取内容
        content = data.get("content", "") or data.get("text", "")
        if isinstance(content, list):
            # 多模态消息 — 提取所有文本段
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            reply_text = " ".join(text_parts) if text_parts else "(多模态消息)"
        else:
            reply_text = str(content).strip()

        if not reply_text:
            await self._send_json(websocket, {
                "type": "error",
                "text": "Empty message content",
            })
            return

        # 回声回复
        print(f"📩 [{client_id[:8]}] 收到: {reply_text[:80]}{'...' if len(reply_text) > 80 else ''}")
        print(f"📤 [{client_id[:8]}] 回复: {reply_text[:80]}{'...' if len(reply_text) > 80 else ''}")

        if streaming_enabled:
            await self._send_streaming_reply(websocket, reply_text)
        else:
            await self._send_json(websocket, {
                "type": "message",
                "text": reply_text,
            })

    async def _send_streaming_reply(self, websocket, text: str) -> None:
        """以流式方式逐 token 发送回复。"""
        # 流式开始
        await self._send_json(websocket, {"type": "stream_start"})

        # 将文本按字符拆分，模拟逐 token 推送
        accumulated = ""
        for char in text:
            accumulated += char
            await self._send_json(websocket, {
                "type": "stream_delta",
                "text": accumulated,
            })
            await asyncio.sleep(0.02)  # 20ms 间隔，模拟真实流式效果

        # 流式结束
        await self._send_json(websocket, {
            "type": "stream_end",
            "text": text,
        })

    # ── 辅助方法 ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_bearer_token(headers: Any) -> str:
        """从请求头中提取 Authorization: Bearer <token>。"""
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):]
        return ""

    @staticmethod
    def _detect_streaming_preference(headers: Any) -> bool:
        """检测客户端是否请求了流式模式。"""
        streaming_val = headers.get("X-Streaming-Enabled", "0")
        return streaming_val.lower() in ("1", "true", "yes")

    @staticmethod
    async def _send_json(websocket, data: dict) -> None:
        """将 data 序列化为 JSON 并通过 websocket 发送。"""
        text = json.dumps(data, ensure_ascii=False)
        await websocket.send(text)


# ── 命令行入口 ──────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Qwenpaw Pet WebSocket 测试服务端（回声模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  %(prog)s                          # 默认 0.0.0.0:8765，无鉴权\n"
            "  %(prog)s --port 8888              # 自定义端口\n"
            "  %(prog)s --token my-secret        # 启用 Bearer 鉴权\n"
            "  %(prog)s --host 127.0.0.1         # 仅监听本地\n"
        ),
    )
    parser.add_argument(
        "--host", default=_DEFAULT_HOST,
        help=f"监听地址（默认: {_DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port", type=int, default=_DEFAULT_PORT,
        help=f"监听端口（默认: {_DEFAULT_PORT})",
    )
    parser.add_argument(
        "--token", default="",
        help="Bearer token，留空则不鉴权",
    )
    return parser.parse_args(argv)


def main() -> int:
    """CLI 入口。"""
    args = _parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    server = QwenpawPetTestServer(
        host=args.host,
        port=args.port,
        token=args.token,
    )

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
