"""将 config.json 中的 url、token、streaming、wake_word、silence_timeout 加载为模块级变量。"""

from __future__ import annotations

import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config() -> dict:
    """加载 config.json 并返回配置字典。"""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 模块级变量 ──────────────────────────────────────────────────────────

_config = _load_config()

url: str = _config["url"]
"""WebSocket 服务器地址，如 ``ws://host:8765``。"""

token: str = _config["token"]
"""Bearer token，用于鉴权。"""

streaming: bool = _config.get("streaming", True)
"""是否开启流式加载（逐 token 推送）。"""

wake_word: str = _config.get("wake_word", "\u4f60\u597d")
"""唤醒词，如 ``"你好"``。"""

silence_timeout: int = _config.get("silence_timeout", 3)
"""静音超时秒数，沉默超过此时间后停止录音。"""

voice_enabled: bool = _config.get("voice_enabled", True)
"""是否启用语音唤醒功能。"""