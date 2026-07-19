"""
基于 Silero VAD (ONNX) 的语音活动检测模块。

通过麦克风实时监听音频流，检测到连续静音超过指定秒数时返回 ``False``。

用法::

    from VAD import QwenpawVAD

    vad = QwenpawVAD()

    # 阻塞等待：不说话持续 3 秒后返回 False
    result = vad.wait_for_silence(3)

    # 在其他线程中可调用 stop() 提前终止
    # vad.stop()
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import urllib.request
from typing import Optional

import numpy as np
import onnxruntime
import sounddevice as sd

logger = logging.getLogger(__name__)

# ── VAD 常量 ─────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
"""音频采样率 (Hz)。"""

FRAME_DURATION_MS = 30
"""每帧时长 (ms)。"""

FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
"""每帧采样数，16000 Hz × 30ms = 480 samples。"""

SILERO_WINDOW_SIZE = 512
"""Silero VAD 模型期望的窗口大小。"""

# ── 模型管理 ─────────────────────────────────────────────────────────────

_SILERO_VAD_URL = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/master/"
    "src/silero_vad/data/silero_vad_16k_op15.onnx"
)
_SILERO_VAD_FILENAME = "silero_vad_16k_op15.onnx"


def _get_default_model_dir() -> str:
    """返回默认模型缓存目录 ``~/.cache/qwenpaw-vad/``。"""
    return os.path.join(os.path.expanduser("~"), ".cache", "qwenpaw-vad")


def _ensure_model(model_dir: Optional[str] = None) -> str:
    """返回模型文件路径，必要时自动下载。

    Args:
        model_dir: 模型文件所在目录。为 ``None`` 时使用默认缓存目录。

    Returns:
        模型文件的完整路径。
    """
    if model_dir is None:
        model_dir = _get_default_model_dir()

    model_path = os.path.join(model_dir, _SILERO_VAD_FILENAME)
    if os.path.isfile(model_path):
        return model_path

    # 自动下载
    os.makedirs(model_dir, exist_ok=True)
    logger.info("Downloading Silero VAD model from %s ...", _SILERO_VAD_URL)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, _SILERO_VAD_FILENAME)
        urllib.request.urlretrieve(_SILERO_VAD_URL, tmp_path)
        import shutil
        shutil.move(tmp_path, model_path)
    logger.info("Silero VAD model ready at %s", model_path)
    return model_path


# ── VAD 检测器 ───────────────────────────────────────────────────────────


class QwenpawVAD:
    """基于 Silero VAD (ONNX) 的实时静音检测器。

    监听麦克风音频，当连续静音时长超过指定秒数时返回 ``False``。

    用法::

        vad = QwenpawVAD(threshold=0.5)

        # 阻塞等待静音 3 秒
        result = vad.wait_for_silence(3)
        print(result)  # False

        # 可在另一线程中提前停止
        # vad.stop()
    """

    def __init__(
        self,
        threshold: float = 0.5,
        model_dir: Optional[str] = None,
    ) -> None:
        """初始化 VAD 检测器。

        Args:
            threshold: 语音概率阈值 (0~1)。
                模型输出 > threshold 视为语音，否则视为静音。
                值越小对静音越敏感（越容易将噪声视为语音）。
                默认 0.5，适合大多数场景。
            model_dir: Silero VAD 模型文件所在目录。
                为 ``None`` 时自动下载到 ``~/.cache/qwenpaw-vad/``。
        """
        model_path = _ensure_model(model_dir)

        self._threshold = threshold
        self._model_dir = os.path.dirname(model_path)

        # ONNX Runtime 配置
        ort_options = onnxruntime.SessionOptions()
        ort_options.inter_op_num_threads = 1
        ort_options.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(
            model_path,
            sess_options=ort_options,
            providers=["CPUExecutionProvider"],
        )

        # 模型元数据
        self._input_name = self._session.get_inputs()[0].name
        self._sr_name = self._session.get_inputs()[1].name

        self._stop_event = threading.Event()
        self._listening = False

    # ── 公共接口 ────────────────────────────────────────────────────────

    def wait_for_silence(self, duration: int) -> bool:
        """监听麦克风，等待连续静音超过指定秒数。

        阻塞运行，直到满足以下任一条件：
        - 连续静音时长 >= ``duration`` 秒 → 返回 ``False``
        - 其他线程调用 ``stop()`` → 返回 ``False``

        Args:
            duration: 连续静音秒数阈值。

        Returns:
            始终返回 ``False``（静音超时或外部终止）。
        """
        self._stop_event.clear()
        self._listening = True

        silence_seconds = 0.0
        audio_buffer = bytearray()

        # Silero VAD 状态（必须跨帧保持）
        h = np.zeros((2, 1, 64), dtype=np.float32)
        c = np.zeros((2, 1, 64), dtype=np.float32)

        def audio_callback(
            indata: sd.ndarray,
            frames: int,
            time_info: sd.TimeInfo,
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                logger.warning("Audio input status: %s", status)
            audio_buffer.extend(indata.tobytes())

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=audio_callback,
                blocksize=SILERO_WINDOW_SIZE,
            ):
                logger.info(
                    "VAD started — silence timeout: %ds, threshold: %.2f",
                    duration,
                    self._threshold,
                )

                while not self._stop_event.is_set():
                    # 从缓冲区取出完整帧
                    while len(audio_buffer) >= SILERO_WINDOW_SIZE * 4:
                        raw = bytes(audio_buffer[: SILERO_WINDOW_SIZE * 4])
                        audio_buffer = audio_buffer[SILERO_WINDOW_SIZE * 4 :]

                        # 转换为 float32 numpy 数组
                        frame = np.frombuffer(raw, dtype=np.float32).reshape(
                            1, SILERO_WINDOW_SIZE
                        )

                        # 送入 Silero VAD 模型推理
                        ort_inputs = {
                            self._input_name: frame,
                            self._sr_name: np.array([SAMPLE_RATE], dtype=np.int64),
                            "h": h,
                            "c": c,
                        }
                        out, h, c = self._session.run(None, ort_inputs)
                        speech_prob = out[0][0]

                        if speech_prob >= self._threshold:
                            # 检测到语音 → 重置静音计时
                            silence_seconds = 0.0
                        else:
                            # 静音 → 累加
                            frame_duration = SILERO_WINDOW_SIZE / SAMPLE_RATE
                            silence_seconds += frame_duration
                            if silence_seconds >= duration:
                                logger.info(
                                    "Silence exceeded %ds (prob=%.4f), "
                                    "returning False",
                                    duration,
                                    speech_prob,
                                )
                                return False

                    time.sleep(0.01)  # 避免忙等

        except sd.PortAudioError as e:
            logger.error("Microphone error (no input device?): %s", e)
            raise
        except Exception as e:
            logger.error("VAD detection error: %s", e)
            raise
        finally:
            self._listening = False
            logger.info("VAD stopped")

        return False  # 外部终止时也返回 False

    def stop(self) -> None:
        """停止静音检测（如果有正在运行的 ``wait_for_silence`` 调用）。"""
        self._listening = False
        self._stop_event.set()

    @property
    def is_listening(self) -> bool:
        """是否正在监听麦克风。"""
        return self._listening

    def __del__(self) -> None:
        """析构时确保停止监听。"""
        if hasattr(self, "_stop_event"):
            self.stop()


# ── 模块级单例 ──────────────────────────────────────────────────────────

vad = QwenpawVAD()
"""模块级 ``QwenpawVAD`` 实例，可直接使用。"""
