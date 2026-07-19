"""
使用 tkinter 创建桌面宠物窗口。

用法::

    class Controller:
        def open_window(self):
            print("打开窗口")

        def close_window(self):
            print("关闭窗口")

    pet = PetWindow(Controller())
    pet.show_main_window()
"""

from __future__ import annotations

import os
import tkinter as tk

from PIL import Image, ImageTk

# ── 常量 ────────────────────────────────────────────────────────────────

_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
_STATES = {
    "沉默": "沉默.png",
    "思考": "思考.png",
    "说话": "说话.png",
}
_DEFAULT_POSITION = (100, 100)
_DRAG_THRESHOLD = 5  # 拖拽阈值（像素），超过此值视为拖拽而非点击


# ── 对话框控制器 ─────────────────────────────────────────────────────────


class DialogController:
    """控制面板控制器，在 PetWindow 点击时打开/关闭一个含 4 个按钮的窗口。

    每个按钮仅触发对应的回调函数，无其他内置行为。
    窗口的打开/关闭由 PetWindow 通过 ``open_window()`` / ``close_window()`` 控制。

    用法::

        ctrl = DialogController()
        ctrl.set_on_setting(lambda: print("设置"))
        ctrl.set_on_open_dialog(lambda: print("打开对话框"))
        ctrl.set_on_close_dialog(lambda: print("关闭对话框"))
        ctrl.set_on_exit(lambda: print("退出"))

        pet = PetWindow(ctrl)
        pet.show_main_window()
    """

    def __init__(self) -> None:
        self._window: tk.Toplevel | None = None
        # 4 个回调属性，默认为 None
        self._on_setting: callable | None = None
        self._on_open_dialog: callable | None = None
        self._on_close_dialog: callable | None = None
        self._on_exit: callable | None = None

    # ── 回调注册方法 ─────────────────────────────────────────────────

    def set_on_setting(self, callback: callable) -> None:
        """注册"设置"按钮点击回调。"""
        self._on_setting = callback

    def set_on_open_dialog(self, callback: callable) -> None:
        """注册"打开对话框"按钮点击回调。"""
        self._on_open_dialog = callback

    def set_on_close_dialog(self, callback: callable) -> None:
        """注册"关闭对话框"按钮点击回调。"""
        self._on_close_dialog = callback

    def set_on_exit(self, callback: callable) -> None:
        """注册"退出"按钮点击回调。"""
        self._on_exit = callback

    # ── 窗口生命周期 ─────────────────────────────────────────────────

    def open_window(self) -> None:
        """打开控制面板窗口，包含"设置""打开对话框""关闭对话框""退出"4 个按钮。"""
        if self._window is not None:
            return

        self._window = tk.Toplevel()
        self._window.title("控制面板")
        self._window.geometry("300x250")
        self._window.resizable(False, False)

        # 让窗口居中
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        x = (screen_w - 300) // 2
        y = (screen_h - 250) // 2
        self._window.geometry(f"+{x}+{y}")

        # 提示标签
        label = tk.Label(self._window, text="请选择一个操作")
        label.pack(pady=20)

        # 4 个按钮 — 仅触发对应的回调
        btn_setting = tk.Button(
            self._window, text="设置", width=20,
            command=lambda: self._on_setting() if self._on_setting else None,
        )
        btn_setting.pack(pady=5)

        btn_open = tk.Button(
            self._window, text="打开对话框", width=20,
            command=lambda: self._on_open_dialog() if self._on_open_dialog else None,
        )
        btn_open.pack(pady=5)

        btn_close = tk.Button(
            self._window, text="关闭对话框", width=20,
            command=lambda: self._on_close_dialog() if self._on_close_dialog else None,
        )
        btn_close.pack(pady=5)

        btn_exit = tk.Button(
            self._window, text="退出", width=20,
            command=lambda: self._on_exit() if self._on_exit else None,
        )
        btn_exit.pack(pady=5)

    def close_window(self) -> None:
        """关闭之前打开的控制面板窗口。"""
        if self._window is not None:
            self._window.destroy()
            self._window = None


# ── 主窗口类 ────────────────────────────────────────────────────────────


class PetWindow:
    """桌面宠物主窗口。

    透明、无边框，只显示一张状态图片。点击图片时交替调用控制器
    的打开/关闭窗口方法。

    Args:
        controller: 具有以下两个方法的对象:
            - ``open_window()``: 点击屏幕时调用，打开新窗口。
            - ``close_window()``: 再次点击时调用，关闭之前打开的窗口。
    """

    def __init__(self, controller) -> None:
        self.controller = controller

        # tkinter 组件
        self.root: tk.Tk | None = None
        self._image_label: tk.Label | None = None

        # 图片缓存
        self._images: dict[str, ImageTk.PhotoImage] = {}
        self._current_state: str = "沉默"

        # 点击状态 (True → 已打开窗口, False → 未打开窗口)
        self._is_open: bool = False

        # 拖拽状态
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_start_win_x: int = 0
        self._drag_start_win_y: int = 0
        self._drag_active: bool = False

    # ── 公共方法 ─────────────────────────────────────────────────────

    def show_main_window(self) -> None:
        """创建并显示主窗口。

        主窗口是透明、无边框、置顶的，仅包含一个图片标签。
        """
        self.root = tk.Tk()

        # 窗口配置 — 透明、无边框、置顶
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", "white")
        except tk.TclError:
            # Linux 不支持 -transparentcolor
            pass
        self.root.configure(bg="white")

        # 设置初始位置
        self.root.geometry(f"+{_DEFAULT_POSITION[0]}+{_DEFAULT_POSITION[1]}")

        # 加载图片
        self._load_images()

        # 创建图片标签
        self._image_label = tk.Label(self.root, bg="white")
        self._image_label.pack()

        # 初始状态
        self.switch_image("沉默")

        # 绑定鼠标事件（拖拽 + 点击）
        self.root.bind("<Button-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<ButtonRelease-1>", self._on_drag_end)

        # 进入主循环
        self.root.mainloop()

    def switch_image(self, state: str) -> None:
        """切换显示的图片。

        Args:
            state: 状态名称，必须是 ``"沉默"``、``"思考"`` 或 ``"说话"`` 之一。
        """
        if state not in self._images:
            return
        if self._image_label is None:
            return

        self._image_label.config(image=self._images[state])
        self._current_state = state

        # 根据图片尺寸调整窗口大小
        img = self._images[state]
        self.root.geometry(f"{img.width()}x{img.height()}"
                           f"+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def close_window(self) -> None:
        """关闭主窗口并清理所有资源。"""
        if self.root is not None:
            self.root.quit()
            self.root.destroy()
            self.root = None
            self._image_label = None
            self._is_open = False

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _load_images(self) -> None:
        """从 ``images/`` 目录加载所有状态图片。"""
        for state, filename in _STATES.items():
            path = os.path.join(_IMAGE_DIR, filename)
            if os.path.isfile(path):
                pil_img = Image.open(path)
                self._images[state] = ImageTk.PhotoImage(pil_img)
            else:
                # 图片缺失时创建占位
                placeholder = tk.PhotoImage(width=1, height=1)
                self._images[state] = placeholder

    def _on_drag_start(self, event) -> None:
        """鼠标按下时记录起始位置。"""
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_start_win_x = self.root.winfo_x()
        self._drag_start_win_y = self.root.winfo_y()
        self._drag_active = False

    def _on_drag_motion(self, event) -> None:
        """鼠标拖动时移动窗口。超过阈值后才实际移动，避免与点击混淆。"""
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y

        if not self._drag_active:
            if abs(dx) > _DRAG_THRESHOLD or abs(dy) > _DRAG_THRESHOLD:
                self._drag_active = True
            else:
                return

        new_x = self._drag_start_win_x + dx
        new_y = self._drag_start_win_y + dy
        self.root.geometry(f"+{new_x}+{new_y}")

    def _on_drag_end(self, event) -> None:
        """鼠标释放时判断：未拖拽则视为点击，触发切换逻辑。"""
        if not self._drag_active:
            self._on_click(event)

    def _on_click(self, _event) -> None:
        """点击图片时的处理：交替调用控制器的打开/关闭窗口方法。"""
        if not self._is_open:
            self.controller.open_window()
            self._is_open = True
        else:
            self.controller.close_window()
            self._is_open = False

# ── 设置控制器 ──────────────────────────────────────────────────────────


class SettingController:
    """设置窗口控制器。

    提供 ``open_window()`` 方法，打开一个设置窗口，允许用户修改
    url、token、streaming、wake_word、silence_timeout，并保存到 ``config.json``。

    用法::

        ctrl = SettingController()
        ctrl.open_window()
    """

    _DEFAULT_CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json",
    )
    _DEFAULT_CONFIG = {
        "url": "ws://localhost:8765",
        "token": "",
        "streaming": True,
        "wake_word": "\u4f60\u597d",
        "silence_timeout": 3,
        "voice_enabled": True,
    }

    def __init__(
        self,
        config_path: str | None = None,
        on_saved: callable | None = None,
    ) -> None:
        """初始化设置控制器。

        Args:
            config_path: config.json 的路径，默认同目录下的 ``config.json``。
            on_saved: 保存成功后回调，接收 ``(url, token, streaming, wake_word, silence_timeout, voice_enabled)``。
        """
        self._config_path = config_path or self._DEFAULT_CONFIG_PATH
        self._on_saved = on_saved
        self._window: tk.Toplevel | None = None

        # 输入控件引用
        self._url_var: tk.StringVar | None = None
        self._token_var: tk.StringVar | None = None
        self._streaming_var: tk.BooleanVar | None = None
        self._wake_word_var: tk.StringVar | None = None
        self._silence_timeout_var: tk.StringVar | None = None
        self._voice_enabled_var: tk.BooleanVar | None = None

    # ── 公共方法 ─────────────────────────────────────────────────────

    def open_window(self) -> None:
        """打开设置窗口，允许修改 url、token、streaming、wake_word、silence_timeout。"""
        if self._window is not None:
            self._window.lift()
            return

        config = self._load_config()

        self._window = tk.Toplevel()
        self._window.title("设置")
        self._window.geometry("350x440")
        self._window.resizable(False, False)

        # 居中
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        x = (screen_w - 350) // 2
        y = (screen_h - 440) // 2
        self._window.geometry(f"+{x}+{y}")

        # URL 输入
        tk.Label(self._window, text="URL:", anchor="w").pack(
            fill="x", padx=20, pady=(15, 0),
        )
        self._url_var = tk.StringVar(
            value=config.get("url", self._DEFAULT_CONFIG["url"]),
        )
        tk.Entry(self._window, textvariable=self._url_var).pack(fill="x", padx=20)

        # Token 输入（密码模式）
        tk.Label(self._window, text="Token:", anchor="w").pack(
            fill="x", padx=20, pady=(10, 0),
        )
        self._token_var = tk.StringVar(
            value=config.get("token", self._DEFAULT_CONFIG["token"]),
        )
        tk.Entry(self._window, textvariable=self._token_var, show="*").pack(
            fill="x", padx=20,
        )

        # 流式模式复选框
        self._streaming_var = tk.BooleanVar(
            value=config.get("streaming", self._DEFAULT_CONFIG["streaming"]),
        )
        tk.Checkbutton(
            self._window, text="使用流式模式", variable=self._streaming_var,
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # 唤醒词输入
        tk.Label(self._window, text="唤醒词:", anchor="w").pack(
            fill="x", padx=20, pady=(10, 0),
        )
        self._wake_word_var = tk.StringVar(
            value=config.get("wake_word", self._DEFAULT_CONFIG["wake_word"]),
        )
        tk.Entry(self._window, textvariable=self._wake_word_var).pack(fill="x", padx=20)

        # 静音超时输入
        tk.Label(self._window, text="静音超时 (秒):", anchor="w").pack(
            fill="x", padx=20, pady=(10, 0),
        )
        self._silence_timeout_var = tk.StringVar(
            value=str(config.get("silence_timeout", self._DEFAULT_CONFIG["silence_timeout"])),
        )
        tk.Entry(self._window, textvariable=self._silence_timeout_var).pack(fill="x", padx=20)

        # 语音唤醒开关
        self._voice_enabled_var = tk.BooleanVar(
            value=config.get("voice_enabled", self._DEFAULT_CONFIG["voice_enabled"]),
        )
        tk.Checkbutton(
            self._window, text="启用语音唤醒", variable=self._voice_enabled_var,
        ).pack(anchor="w", padx=20, pady=(10, 0))

        # 按钮区域
        btn_frame = tk.Frame(self._window)
        btn_frame.pack(pady=(20, 0))

        tk.Button(
            btn_frame, text="保存", width=10, command=self._on_save,
        ).pack(side="left", padx=5)
        tk.Button(
            btn_frame, text="取消", width=10, command=self._on_cancel,
        ).pack(side="left", padx=5)

        # 窗口关闭按钮 → 取消
        self._window.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        """从 config.json 读取配置，文件不存在或解析失败时返回默认值。"""
        import json

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(self._DEFAULT_CONFIG)

    def _save_config(
        self, url: str, token: str, streaming: bool,
        wake_word: str, silence_timeout: int, voice_enabled: bool,
    ) -> None:
        """将配置写入 config.json。"""
        import json

        config = {
            "url": url,
            "token": token,
            "streaming": streaming,
            "wake_word": wake_word,
            "silence_timeout": silence_timeout,
            "voice_enabled": voice_enabled,
        }
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _on_save(self) -> None:
        """保存按钮回调：收集输入值，写入文件，关闭窗口。"""
        url = self._url_var.get().strip() if self._url_var else ""
        token = self._token_var.get() if self._token_var else ""
        streaming = self._streaming_var.get() if self._streaming_var else True
        wake_word = self._wake_word_var.get().strip() if self._wake_word_var else ""
        try:
            silence_timeout = int(self._silence_timeout_var.get().strip()) if self._silence_timeout_var else 3
        except ValueError:
            silence_timeout = 3
        voice_enabled = self._voice_enabled_var.get() if self._voice_enabled_var else True

        self._save_config(url, token, streaming, wake_word, silence_timeout, voice_enabled)

        if self._on_saved:
            self._on_saved(url, token, streaming, wake_word, silence_timeout, voice_enabled)

        self._close_window()

    def _on_cancel(self) -> None:
        """取消按钮回调：不保存，直接关闭窗口。"""
        self._close_window()

    def _close_window(self) -> None:
        """关闭设置窗口并清理引用。"""
        if self._window is not None:
            self._window.destroy()
            self._window = None


# ── 输入/显示对话框控制器 ──────────────────────────────────────────────


class ChatInputController:
    """输入/显示对话框控制器。

    提供一个可切换输入/显示模式的窗口，适用于对话场景：
    - 输入模式：用户可在纯白色输入框中输入文本。
    - 显示模式：输入框变为只读显示框，展示指定的字符串。
    - 点击显示框可重新切回输入模式。

    用法::

        def on_submit(text: str) -> None:
            print(f"用户输入: {text}")

        ctrl = ChatInputController(callback=on_submit)
        ctrl.open_window()
        ctrl.display_text("你好！请问有什么可以帮你的？")
    """

    def __init__(self, callback: callable | None = None) -> None:
        """初始化输入对话框控制器。

        Args:
            callback: 用户点击右下角按钮时的回调，接收输入文本作为参数。
        """
        self._callback = callback
        self._window: tk.Toplevel | None = None
        self._text: tk.Text | None = None
        self._submit_btn: tk.Button | None = None
        self._input_mode: bool = True

    # ── 公共方法 ─────────────────────────────────────────────────────

    def open_window(self) -> None:
        """打开输入对话框窗口。

        窗口包含一个纯白色输入框（占满整个窗口）和右下角的提交按钮。
        """
        if self._window is not None:
            self._window.lift()
            return

        self._window = tk.Toplevel()
        self._window.title("输入")
        self._window.geometry("400x300")
        self._window.resizable(True, True)

        # 居中
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        x = (screen_w - 400) // 2
        y = (screen_h - 300) // 2
        self._window.geometry(f"+{x}+{y}")

        # 纯白色输入框，填满整个窗口
        self._text = tk.Text(
            self._window,
            bg="white",
            wrap="word",
            relief="flat",
            padx=10,
            pady=10,
        )
        self._text.pack(fill="both", expand=True)

        # 绑定点击事件（用于从显示模式切回输入模式）
        self._text.bind("<Button-1>", self._on_text_click)

        # 右下角的提交按钮
        self._submit_btn = tk.Button(
            self._window,
            text="发送",
            command=self._on_submit,
        )
        self._submit_btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        # 窗口关闭按钮 → 清理资源
        self._window.protocol("WM_DELETE_WINDOW", self.close_window)

        self._input_mode = True

    def display_text(self, text: str) -> None:
        """将输入框切换为显示框，显示指定的文本。

        调用此方法后输入框变为只读显示模式，显示传入的字符串。
        点击显示框可重新切回输入模式。

        Args:
            text: 要显示的字符串。
        """
        if self._text is None:
            return

        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.config(state=tk.DISABLED)

        self._input_mode = False

    def close_window(self) -> None:
        """关闭窗口并清理所有资源。"""
        if self._window is not None:
            self._window.destroy()
            self._window = None
            self._text = None
            self._submit_btn = None

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        """提交按钮回调：获取输入文本，调用回调，清除输入框并切回输入模式。"""
        if self._text is None:
            return

        content = self._text.get("1.0", tk.END).rstrip("\n")

        if self._callback:
            self._callback(content)

        # 清除输入框并切回输入模式
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._input_mode = True

    def _on_text_click(self, _event) -> None:
        """点击文本区域的处理：如果在显示模式，切换回输入模式。"""
        if self._input_mode or self._text is None:
            return

        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._input_mode = True

# ── 单元测试 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 演示 DialogController + SettingController
    setting_ctrl = SettingController(
        on_saved=lambda url, token, streaming: print(
            f"[保存] url={url}, token={'*' * len(token)}, streaming={streaming}",
        ),
    )
    ctrl = DialogController()
    ctrl.set_on_setting(setting_ctrl.open_window)
    ctrl.set_on_open_dialog(lambda: print("[回调] 打开对话框 被点击"))
    ctrl.set_on_close_dialog(lambda: print("[回调] 关闭对话框 被点击"))
    ctrl.set_on_exit(lambda: print("[回调] 退出 被点击"))

    pet = PetWindow(ctrl)
    pet.show_main_window()