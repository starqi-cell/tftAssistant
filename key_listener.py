import time
from pynput import keyboard


# 键盘监听器回调函数
def on_press(key, assistant, float_ui):
    try:
        # 手动触发一次检测
        if hasattr(key, 'char') and key.char == 'd' and assistant.enabled:
            time.sleep(0.2)
            assistant.process_once()
        # 切换辅助开关
        elif key == keyboard.Key.f1:
            assistant.toggle()
        # 显示/隐藏浮动控件
        elif key == keyboard.Key.f2:
            if float_ui.isVisible(): float_ui.hide()
            else: float_ui.show()
    except AttributeError:
        pass


def start_key_listener(assistant, float_ui):
    listener = keyboard.Listener(on_press=lambda key: on_press(key, assistant, float_ui))
    listener.daemon = True
    listener.start()
