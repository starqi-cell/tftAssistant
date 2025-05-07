import os
import sys
import threading
from PyQt5 import QtWidgets
from assistant import ShopAssistant
from ui_floating import FloatingWidget
from key_listener import start_key_listener


if __name__ == "__main__":
    # 点击偏移
    click_offset = (70, 60)

    #模型导入
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)

    model_rel = os.path.join('runs', 'detect', 'train2', 'weights', 'best.pt')
    model_path = os.path.join(base_path, model_rel)

    # 初始化助手和UI
    assistant = ShopAssistant(model_path, click_offset=click_offset)
    app = QtWidgets.QApplication([])
    float_ui = FloatingWidget(assistant)
    assistant.ui_callback = float_ui.update

    # 启动键盘监听线程
    start_key_listener(assistant, float_ui)

    # 启动检测线程
    thread = threading.Thread(target=assistant.run, daemon=True)
    thread.start()

    # 启动UI主循环
    sys.exit(app.exec_())
