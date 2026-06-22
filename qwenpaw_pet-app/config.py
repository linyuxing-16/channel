"""将config.json中的配置的url,token,是否开启流式加载为变量"""

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

stream: bool = _config.get("stream", True)
"""是否开启流式加载（逐 token 推送）。"""