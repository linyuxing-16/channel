from __future__ import annotations

import asyncio
import threading

from config import token, url
from websocket_pet import QwenpawPetClient

# 创建一个队列，用于存储从 WebSocket 接收到的消息
message_queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()


def enqueue_callback(content: str, is_end: bool) -> None:
    """回调函数：将消息内容及是否为结束标记放入队列。"""
    message_queue.put_nowait((content, is_end))


# 使用 url、token 和往队列添加字符串消息的回调函数为参数创建 QwenpawPetClient 实例
client = QwenpawPetClient(
    url=url,
    token=token,
    callback=enqueue_callback,
)

import windows

# 创建一个 DialogController 实例，用于控制桌面宠物窗口的交互面板
dialog_controller = windows.DialogController()

# 使用 DialogController 实例来初始化 PetWindow
pet_window = windows.PetWindow(dialog_controller)
setting_controller = windows.SettingController()
dialog_controller.set_on_setting(setting_controller.open_window)

dialog_controller.set_on_exit(pet_window.close_window)

# 定义一个异步发送函数，通过 client.send_message 实现消息发送
async def send_message(text: str) -> None:
    """通过 WebSocket 客户端发送文本消息。"""
    await client.send_message(text)


def send_message_sync(text: str) -> None:
    """同步包装 send_message，供 tkinter 回调使用。"""
    # 发送时把状态切换成思考
    pet_window.switch_image("思考")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环，使用 asyncio.run()
        asyncio.run(send_message(text))
    else:
        # 有运行中的事件循环，创建任务
        asyncio.create_task(send_message(text))


# 使用发送函数作为参数创建 ChatInputController 实例
chat_input_controller = windows.ChatInputController(callback=send_message_sync) #在发送时调用pet_window.switch_image把状态切换成思考

# 将 chat_input_controller 的打开和关闭方法分别传递给 set_on_open_dialog、set_on_close_dialog
dialog_controller.set_on_open_dialog(chat_input_controller.open_window)
dialog_controller.set_on_close_dialog(chat_input_controller.close_window)

async def consume_messages() -> None:
    """从消息队列消费消息并更新 UI。

    从 message_queue 中取出 (content, is_end) 元组，
    通过 root.after 调度 tkinter 更新到主线程执行。
    """
    while True:
        content, is_end = await message_queue.get()
        if is_end:
            # 接收到停止消息，切换到沉默状态
            pet_window.root.after(0, pet_window.switch_image, "沉默")
        else:
            # 有新消息，切换到说话状态并显示文本
            pet_window.root.after(0, _display_incoming_message, content)
            pet_window.root.after(0, pet_window.switch_image, "说话")


def _display_incoming_message(content: str) -> None:
    """打开输入框（如未打开）并显示收到的文本。"""
    chat_input_controller.open_window()
    chat_input_controller.display_text(content)


if __name__ == "__main__":
    # 创建新的事件循环并在守护线程中运行
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()

    # 调度 connect 和 consume_messages 协程
    asyncio.run_coroutine_threadsafe(client.connect(), loop)
    asyncio.run_coroutine_threadsafe(consume_messages(), loop)

    # 启动 tkinter 主循环（主线程阻塞）
    pet_window.show_main_window()

    # 窗口关闭后清理
    loop.call_soon_threadsafe(loop.stop)