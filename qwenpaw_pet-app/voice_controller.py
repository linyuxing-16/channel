"""
语音唤醒 → 录音 → VAD 静音检测 → 编码发送 编排模块。

整合 KWS（关键词检测）和 VAD（语音活动检测），实现：
1. 持续监听唤醒词（KWS 阶段）
2. 唤醒后录音 + VAD 静音检测（单 InputStream 共享）
3. 静音超时 → 编码为 WAV/base64 → 回调通知

用法::

    from voice_controller import VoiceController

    def on_audio_ready(b64: str) -> None:
        print(f"Audio ready, {len(b64)} bytes base64")

    def on_state(state: str) -> None:
        print(f"State: {state}")

    vc = VoiceController(
        wake_word="你好",
        silence_timeout=3,
        on_audio_ready=on_audio_ready,
        on_state_change=on_state,
    )
    vc.start()
    # ...
    vc.stop()
"""

from __future__ import annotations

import base64
import io
import logging
import threading
import time
import wave
from typing import Callable, Optional

import numpy as np
import onnxruntime
import sounddevice as sd

from KWS import QwenpawKWS

logger = logging.getLogger(__name__)

# ── 音频常量 ──────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
"""录音采样率 (Hz)。"""

VAD_WINDOW_SIZE = 512
"""Silero VAD 每帧采样数。"""


# ── VoiceController ───────────────────────────────────────────────────


class VoiceController:
    """语音唤醒 → 录音 → 发送 编排器。

    工作流程::

        start()
          └─ KWS 持续监听唤醒词
                └─ 检测到唤醒词 → stop KWS → 开始录音 + VAD
                      └─ 连续静音 ≥ silence_timeout 秒
                            ├─ on_state_change("思考")
                            ├─ 编码为 WAV/base64
                            └─ on_audio_ready(base64)
                               → 回到 start() 继续监听
    """

    def __init__(
        self,
        wake_word: str = "你好",
        silence_timeout: int = 3,
        on_audio_ready: Optional[Callable[[str], None]] = None,
        on_state_change: Optional[Callable[[str], None]] = None,
        vad_threshold: float = 0.5,
    ) -> None:
        """初始化 VoiceController。

        Args:
            wake_word: 唤醒词，如 ``"你好"``。
            silence_timeout: 静音超时秒数。
            on_audio_ready: 音频就绪回调，接收 base64 编码的 WAV 字符串。
            on_state_change: 状态变更回调，接收 ``"沉默"`` / ``"思考"`` / ``"说话"``。
            vad_threshold: VAD 语音概率阈值 (0~1)，大于此值视为语音。
        """
        self._wake_word = wake_word
        self._silence_timeout = silence_timeout
        self._vad_threshold = vad_threshold
        self._on_audio_ready = on_audio_ready
        self._on_state_change = on_state_change

        # KWS 实例
        self._kws = QwenpawKWS()

        # VAD ONNX session（与 KWS 共享模型管理理念，但独立使用）
        self._vad_session: Optional[onnxruntime.InferenceSession] = None
        self._vad_input_name: Optional[str] = None
        self._vad_sr_name: Optional[str] = None

        # 录音线程控制
        self._recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 是否正在监听唤醒词
        self._listening = False

    # ── 公共接口 ─────────────────────────────────────────────────────

    def start(self) -> None:
        """开始监听唤醒词。"""
        if self._listening:
            return
        self._listening = True
        self._stop_event.clear()
        self._kws.listen_for_keyword(self._wake_word, self._on_wake_word)
        logger.info("VoiceController started, listening for '%s'", self._wake_word)

    def stop(self) -> None:
        """停止所有监听和录音。"""
        self._listening = False
        self._kws.stop()
        self._stop_recording()
        logger.info("VoiceController stopped")

    def update_config(
        self,
        wake_word: Optional[str] = None,
        silence_timeout: Optional[int] = None,
    ) -> None:
        """动态更新配置（下次唤醒时生效）。

        Args:
            wake_word: 新的唤醒词。
            silence_timeout: 新的静音超时秒数。
        """
        if wake_word is not None:
            self._wake_word = wake_word
            # 如果正在监听，重启 KWS
            if self._listening:
                self._kws.stop()
                self._kws.listen_for_keyword(self._wake_word, self._on_wake_word)
                logger.info("Wake word updated to '%s'", self._wake_word)
        if silence_timeout is not None:
            self._silence_timeout = silence_timeout
            logger.info("Silence timeout updated to %ds", silence_timeout)

    @property
    def is_listening(self) -> bool:
        """是否正在监听唤醒词。"""
        return self._listening

    @property
    def is_recording(self) -> bool:
        """是否正在录音。"""
        return self._recording

    # ── 唤醒回调 ─────────────────────────────────────────────────────

    def _on_wake_word(self, keyword: str) -> None:
        """唤醒词检测到后的回调。

        1. 停止 KWS（释放麦克风）
        2. 启动录音 + VAD 线程
        """
        logger.info("Wake word detected: '%s'", keyword)
        self._kws.stop()

        # 启动录音线程
        self._stop_event.clear()
        self._record_thread = threading.Thread(
            target=self._record_and_vad,
            daemon=True,
            name="qwenpaw-record",
        )
        self._record_thread.start()

    # ── 录音 + VAD ──────────────────────────────────────────────────

    def _ensure_vad_session(self) -> None:
        """确保 VAD ONNX session 已初始化（延迟初始化）。"""
        if self._vad_session is not None:
            return

        from VAD import _ensure_model as ensure_vad_model

        model_path = ensure_vad_model()
        ort_options = onnxruntime.SessionOptions()
        ort_options.inter_op_num_threads = 1
        ort_options.intra_op_num_threads = 1
        self._vad_session = onnxruntime.InferenceSession(
            model_path,
            sess_options=ort_options,
            providers=["CPUExecutionProvider"],
        )
        self._vad_input_name = self._vad_session.get_inputs()[0].name
        self._vad_sr_name = self._vad_session.get_inputs()[1].name
        logger.debug("VAD ONNX session initialized")

    def _record_and_vad(self) -> None:
        """录音 + VAD 主循环。

        使用单个 sd.InputStream 同时做两件事：
        - 将原始 float32 PCM 追加到 ``audio_buffer``
        - 每帧送入 Silero VAD 推理以检测静音

        连续静音 >= ``silence_timeout`` 秒后：
        1. 停止录音
        2. 调用 ``on_state_change("思考")``
        3. 编码为 WAV/base64 → 调用 ``on_audio_ready(b64)``
        """
        self._ensure_vad_session()
        self._recording = True

        audio_buffer = bytearray()
        silence_seconds = 0.0

        # Silero VAD 状态（必须跨帧保持）
        h = np.zeros((2, 1, 64), dtype=np.float32)
        c = np.zeros((2, 1, 64), dtype=np.float32)

        def audio_callback(
            indata: sd.ndarray,
            frames: int,
            time_info: sd.TimeInfo,
            status: sd.CallbackFlags,
        ) -> None:
            nonlocal silence_seconds

            if status:
                logger.warning("Audio input status: %s", status)

            # 1) 保存音频数据到缓冲区
            audio_buffer.extend(indata.tobytes())

            # 2) VAD 推理 — 每帧评估语音概率
            # 等待凑满 VAD_WINDOW_SIZE 个样本
            if len(audio_buffer) >= VAD_WINDOW_SIZE * 4:
                # 取前 VAD_WINDOW_SIZE 个样本用于 VAD
                raw = bytes(audio_buffer[: VAD_WINDOW_SIZE * 4])
                frame = np.frombuffer(raw, dtype=np.float32).reshape(
                    1, VAD_WINDOW_SIZE
                )

                ort_inputs = {
                    self._vad_input_name: frame,
                    self._vad_sr_name: np.array([SAMPLE_RATE], dtype=np.int64),
                    "h": h,
                    "c": c,
                }
                out, h_new, c_new = self._vad_session.run(None, ort_inputs)  # type: ignore
                speech_prob = out[0][0]
                h, c = h_new, c_new

                if speech_prob >= self._vad_threshold:
                    silence_seconds = 0.0  # 有语音，重置静音计时
                else:
                    frame_duration = VAD_WINDOW_SIZE / SAMPLE_RATE
                    silence_seconds += frame_duration

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=audio_callback,
                blocksize=VAD_WINDOW_SIZE,
            ):
                logger.info(
                    "Recording started, silence timeout: %ds",
                    self._silence_timeout,
                )

                while not self._stop_event.is_set() and silence_seconds < self._silence_timeout:
                    time.sleep(0.01)

        except sd.PortAudioError as e:
            logger.error("Microphone error during recording: %s", e)
            self._recording = False
            # 出错后重新开始监听
            self._resume_listening()
            return
        except Exception as e:
            logger.error("Recording error: %s", e)
            self._recording = False
            self._resume_listening()
            return

        self._recording = False
        logger.info(
            "Recording stopped (silence=%.2fs/%ds, buffer=%d bytes)",
            silence_seconds,
            self._silence_timeout,
            len(audio_buffer),
        )

        # 如果没有采集到有效音频，直接返回监听模式
        if len(audio_buffer) < VAD_WINDOW_SIZE * 4:
            logger.warning("Audio buffer too small, skipping send")
            self._resume_listening()
            return

        # 切为"思考"状态（等价于文字发送行为）
        if self._on_state_change:
            self._on_state_change("思考")

        # 编码并发送
        try:
            wav_b64 = self._float32_to_wav_base64(bytes(audio_buffer))
            if self._on_audio_ready:
                self._on_audio_ready(wav_b64)
            logger.info("Audio sent (%d bytes raw → %d chars base64)",
                        len(audio_buffer), len(wav_b64))
        except Exception as e:
            logger.error("Audio encoding/send error: %s", e)

        # 完成后重新开始监听
        self._resume_listening()

    # ── 音频编码 ─────────────────────────────────────────────────────

    @staticmethod
    def _float32_to_wav_base64(audio_bytes: bytes) -> str:
        """将 float32 PCM 原始音频转换为 base64 编码的 WAV 字符串。

        处理流程: float32 PCM → int16 PCM → WAV 容器 → base64。

        Args:
            audio_bytes: float32 PCM 原始音频数据（16kHz 单声道）。

        Returns:
            base64 编码的 WAV 音频字符串。
        """
        samples = np.frombuffer(audio_bytes, dtype=np.float32)
        # 裁剪并转换为 int16
        samples = np.clip(samples, -1.0, 1.0)
        int16_samples = (samples * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(int16_samples.tobytes())

        return base64.b64encode(buf.getvalue()).decode("ascii")

    # ── 内部辅助 ─────────────────────────────────────────────────────

    def _stop_recording(self) -> None:
        """停止录音线程。"""
        self._stop_event.set()
        if self._record_thread is not None and self._record_thread.is_alive():
            self._record_thread.join(timeout=3)
            self._record_thread = None
        self._recording = False

    def _resume_listening(self) -> None:
        """录音/发送完成后，重新开始监听唤醒词。"""
        if not self._listening:
            return
        logger.info("Resuming KWS listening for '%s'", self._wake_word)
        self._kws.listen_for_keyword(self._wake_word, self._on_wake_word)

    def __del__(self) -> None:
        """析构时确保清理。"""
        if hasattr(self, "_stop_event"):
            self.stop()
