"""
基于 sherpa-onnx 的关键词检测（KWS）模块。

通过麦克风实时监听音频流，检测到预设关键词时触发回调。

用法::

    from KWS import QwenpawKWS

    def on_keyword(keyword: str) -> None:
        print(f"检测到关键词: {keyword}")

    kws = QwenpawKWS()
    kws.listen_for_keyword("你好", on_keyword)
    # ... 程序运行中，说"你好"触发回调 ...
    kws.stop()
"""

from __future__ import annotations

import logging
import os
import tarfile
import tempfile
import threading
import time
from typing import Callable, Optional

import sherpa_onnx

logger = logging.getLogger(__name__)

# ── 默认模型常量 ──────────────────────────────────────────────────────
# 注意：用户原本倾向 1.1M 模型，但 sherpa-onnx kws-models 发布页中
# 不存在该版本，因此采用 3.3M mobile 模型（轻量 int8 量化版）。

_MODEL_NAME = "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01-mobile"
_MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"kws-models/{_MODEL_NAME}.tar.bz2"
)

# 模型内各文件相对于解压后目录的路径
_MODEL_FILES = {
    "encoder": "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
    "decoder": "decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
    "joiner": "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
    "tokens": "tokens.txt",
    "keywords": "keywords.txt",
}

_SAMPLE_RATE = 16000
_CHUNK_SIZE = int(0.1 * _SAMPLE_RATE)  # 每次读取 100ms 音频


# ── 模型下载与路径管理 ──────────────────────────────────────────────


def _get_default_cache_dir() -> str:
    """返回默认模型缓存目录 ``~/.cache/qwenpaw-kws/{model_name}/``。"""
    return os.path.join(
        os.path.expanduser("~"), ".cache", "qwenpaw-kws", _MODEL_NAME
    )


def _download_and_extract(url: str, dest_dir: str) -> None:
    """从 URL 下载 ``.tar.bz2`` 并解压到 ``dest_dir``。"""
    import urllib.request

    with tempfile.TemporaryDirectory() as tmpdir:
        tarball_path = os.path.join(tmpdir, "model.tar.bz2")
        logger.info("Downloading model from %s ...", url)
        urllib.request.urlretrieve(url, tarball_path)
        logger.info("Download complete.")

        logger.info("Extracting to %s ...", dest_dir)

        # 解压后目录结构: tmp_extract/{_MODEL_NAME}/...
        # 将内容提升到 dest_dir 顶层
        tmp_extract = os.path.join(tmpdir, "extracted")
        os.makedirs(tmp_extract, exist_ok=True)

        with tarfile.open(tarball_path, "r:bz2") as tar:
            tar.extractall(path=tmp_extract)

        extracted_subdir = os.path.join(tmp_extract, _MODEL_NAME)
        if not os.path.isdir(extracted_subdir):
            raise FileNotFoundError(
                f"Expected directory '{_MODEL_NAME}' not found in tarball"
            )

        import shutil

        os.makedirs(dest_dir, exist_ok=True)

        # 移动所有文件到 dest_dir（使用 shutil.move 而非 os.rename，
        # 因为 /tmp 和 ~/.cache 可能不在同一文件系统）
        for item in os.listdir(extracted_subdir):
            src = os.path.join(extracted_subdir, item)
            dst = os.path.join(dest_dir, item)
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            shutil.move(src, dst)

    # 验证必需文件
    for key, fname in _MODEL_FILES.items():
        path = os.path.join(dest_dir, fname)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Required model file '{fname}' not found in {dest_dir}"
            )

    logger.info("Model ready at %s", dest_dir)


def _ensure_model(model_dir: Optional[str] = None) -> str:
    """返回有效的模型目录路径，必要时自动下载。"""
    if model_dir is not None:
        # 用户指定路径 → 验证文件是否存在
        for key, fname in _MODEL_FILES.items():
            path = os.path.join(model_dir, fname)
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f"Required model file '{fname}' not found at {path}. "
                    f"Please ensure all model files exist in {model_dir}"
                )
        return model_dir

    # 自动下载到缓存
    cache_dir = _get_default_cache_dir()
    required = [os.path.join(cache_dir, fname) for fname in _MODEL_FILES.values()]
    if not all(os.path.isfile(p) for p in required):
        logger.info("Model not found in cache, downloading...")
        _download_and_extract(_MODEL_URL, cache_dir)
    return cache_dir


# ── 关键词检测器 ────────────────────────────────────────────────────


class QwenpawKWS:
    """基于 sherpa-onnx 的实时关键词检测器。

    通过麦克风持续监听音频，检测到预设关键词时调用回调。
    采用"持续监听"模式：检测到关键词后自动重置，继续下一轮检测。

    用法::

        def callback(kw: str) -> None:
            print(f"Detected: {kw}")

        kws = QwenpawKWS()
        kws.listen_for_keyword("你好", callback)
        # ... 程序运行中 ...
        kws.stop()
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        keywords_threshold: float = 0.25,
        num_threads: int = 2,
        provider: str = "cpu",
    ) -> None:
        """初始化关键词检测器。

        Args:
            model_dir: 模型文件目录。为 ``None`` 时自动下载到
                ``~/.cache/qwenpaw-kws/{model_name}/``。
            keywords_threshold: 触发阈值 (0~1)。值越大越难触发，默认 0.25。
            num_threads: ONNX Runtime 线程数。
            provider: 执行提供者。可选 ``"cpu"``, ``"cuda"``, ``"coreml"``。
        """
        model_dir = _ensure_model(model_dir)

        self._spotter = sherpa_onnx.KeywordSpotter(
            tokens=os.path.join(model_dir, _MODEL_FILES["tokens"]),
            encoder=os.path.join(model_dir, _MODEL_FILES["encoder"]),
            decoder=os.path.join(model_dir, _MODEL_FILES["decoder"]),
            joiner=os.path.join(model_dir, _MODEL_FILES["joiner"]),
            keywords_file=os.path.join(model_dir, _MODEL_FILES["keywords"]),
            num_threads=num_threads,
            keywords_threshold=keywords_threshold,
            provider=provider,
        )

        self._model_dir = model_dir

        self._listening = False
        self._callback: Optional[Callable[[str], None]] = None
        self._keyword: Optional[str] = None
        self._processed_keyword: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── 公共接口 ────────────────────────────────────────────────────

    def listen_for_keyword(
        self,
        keyword: str,
        callback: Callable[[str], None],
    ) -> None:
        """开始监听指定关键词（持续模式）。

        启动后台线程读取麦克风音频，检测到关键词时调用 ``callback(keyword)``，
        然后自动重置并继续监听。

        Args:
            keyword: 要检测的关键词，如 ``"你好"``、``"小爱同学"``。
            callback: 检测到关键词后的回调，接收关键词字符串作为唯一参数。
        """
        # 如果已在监听则先停止
        self.stop()

        self._keyword = keyword
        self._processed_keyword = self._preprocess_keyword(
            keyword,
            os.path.join(self._model_dir, _MODEL_FILES["tokens"]),
        )
        self._callback = callback
        self._listening = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="qwenpaw-kws",
        )
        self._thread.start()

    def stop(self) -> None:
        """停止关键词监听。"""
        self._listening = False
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def model_dir(self) -> str:
        """模型文件路径。"""
        return self._model_dir

    @property
    def is_listening(self) -> bool:
        """是否正在监听麦克风。"""
        return self._listening

    @property
    def spotter(self) -> sherpa_onnx.KeywordSpotter:
        """底层 ``sherpa_onnx.KeywordSpotter`` 实例。"""
        return self._spotter

    # ── 内部方法 ────────────────────────────────────────────────────

    @staticmethod
    def _preprocess_keyword(keyword: str, tokens_path: str) -> str:
        """将中文关键词转换为 sherpa-onnx 内联格式。

        该模型使用 ppinyin（声母+韵母）token 类型，需要借助
        ``sherpa_onnx.utils.text2token`` 将汉字转为拼音 token。

        返回格式: ``"n ǐ h ǎo @你好"``

        例::

            "你好"      → ``"n ǐ h ǎo @你好"``
            "小爱同学"  → ``"x iǎo ài t óng x ué @小爱同学"``
        """
        from sherpa_onnx.utils import text2token

        tokens = text2token([keyword], tokens_path, tokens_type="ppinyin")
        if not tokens or not tokens[0]:
            logger.warning(
                "Failed to encode keyword '%s', falling back to raw text",
                keyword,
            )
            return keyword

        pinyin_tokens = " ".join(tokens[0])
        return f"{pinyin_tokens} @{keyword}"

    def _detection_loop(self) -> None:
        """后台线程主循环：麦克风 → sherpa-onnx 检测 → 回调。"""
        import sounddevice as sd

        kw = self._processed_keyword
        logger.debug("Processed keyword for sherpa-onnx: %r", kw)

        # 创建 OnlineStream 并注入内联关键词
        stream = self._spotter.create_stream(kw)

        # sd.InputStream 回调：将音频数据送入 OnlineStream
        def audio_callback(
            indata: sd.ndarray,
            frames: int,
            time_info: sd.TimeInfo,
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                logger.warning("Audio input status: %s", status)
            samples = indata.reshape(-1)
            stream.accept_waveform(_SAMPLE_RATE, samples)

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=audio_callback,
                blocksize=_CHUNK_SIZE,
            ):
                logger.info(
                    "Listening for keyword '%s' (processed: %r) ...",
                    self._keyword,
                    kw,
                )

                while not self._stop_event.is_set():
                    if self._spotter.is_ready(stream):
                        self._spotter.decode_stream(stream)
                        result = self._spotter.get_result(stream)
                        if result:
                            logger.info("Keyword detected: %s", result)
                            self._spotter.reset_stream(stream)
                            if self._callback is not None:
                                self._callback(self._keyword)
                    time.sleep(0.01)  # 避免忙等

        except sd.PortAudioError as e:
            logger.error(
                "Microphone error (no input device?): %s", e
            )
            raise
        except Exception as e:
            logger.error("KWS detection error: %s", e)
            raise
        finally:
            self._listening = False
            logger.info("KWS stopped listening")

    def __del__(self) -> None:
        """析构时确保停止监听。"""
        if hasattr(self, "_stop_event"):
            self.stop()
