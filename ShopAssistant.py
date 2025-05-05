import sys
import time
import logging
import threading
import pyautogui
from ultralytics import YOLO
import numpy as np
import win32api
import win32con
import cv2
import win32gui
from pynput import keyboard
from PyQt5 import QtCore, QtGui, QtWidgets
import os, sys

# 主逻辑：商店助手
class ShopAssistant:
    def __init__(self, model_path: str, click_offset=(0, 0), poll_interval=0.0, startup_delay=0.0):
        # 参考分辨率：训练时的全屏大小
        self.REF_W, self.REF_H = 1920, 1080
        # 加载YOLO模型
        self.model = YOLO(model_path)
        #点击偏移
        self.click_offset = click_offset
        #检测周期
        self.poll_interval = poll_interval
        #启动延迟
        self.startup_delay = startup_delay
        # 是否启用检测功能
        self.enabled = False
        # UI界面的回调函数
        self.ui_callback = None
        self._local = threading.local()

        # 日志初始化
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    # 获取LOL游戏窗口的屏幕区域
    def get_game_window_region(self):
        hwnd = win32gui.FindWindow(None, "League of Legends (TM) Client")
        if hwnd != 0:
            client_rect = win32gui.GetClientRect(hwnd)
            pt_origin = win32gui.ClientToScreen(hwnd, (0, 0))
            pt_end = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
            left, top = pt_origin
            width = pt_end[0] - pt_origin[0]
            height = pt_end[1] - pt_origin[1]
            return (left, top, width, height)
        else:
            return None

    # 单帧处理逻辑：截图 -> 目标检测 -> 计算点击位置 -> 点击
    def process_once(self):
        region = self.get_game_window_region()
        if region is None:
            logging.warning("未找到游戏窗口，跳过此帧处理")
            return

        # 只截取游戏窗口客户区
        screenshot = pyautogui.screenshot(region=region)
        original_pos = win32api.GetCursorPos()

        img0 = np.array(screenshot)[:, :, ::-1]
        h0, w0 = img0.shape[:2]
        img = cv2.resize(img0, (self.REF_W, self.REF_H))
        results = self.model.predict(source=img, conf=0.4, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()

        # 反算回原始窗口区域中的坐标
        scale_x = w0 / self.REF_W
        scale_y = h0 / self.REF_H
        centers = []
        for x1, y1, x2, y2 in boxes:
            cx = (x1 + x2) / 2 * scale_x + region[0]
            cy = (y1 + y2) / 2 * scale_y + region[1]
            centers.append((int(cx), int(cy)))

        # 去重
        filtered = []
        for pt in centers:
            if all(np.linalg.norm(np.array(pt) - np.array(fp)) >= 100 for fp in filtered):
                filtered.append(pt)

        if not filtered:
            return
        # 点击检测到的目标
        for cx, cy in filtered:
            # 移动光标
            win32api.SetCursorPos((cx, cy))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            time.sleep(0.08)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            logging.info(f"点击了位置 {(cx, cy)}的检测目标")
            time.sleep(0.02)
            win32api.SetCursorPos(original_pos)


        win32api.SetCursorPos(original_pos)




    # 主循环逻辑
    def run(self):
        logging.info(f"三秒后开始识别: {self.startup_delay}s...")
        time.sleep(self.startup_delay)
        while True:
            if self.enabled:
                start=time.time()
                self.process_once()
                alltime=time.time()-start
                logging.info(f"检测耗时{alltime}s")

    # 辅助开关切换
    def toggle(self):
        self.enabled = not self.enabled
        if self.ui_callback:
            self.ui_callback()
        logging.info("辅助已开启" if self.enabled else "辅助已关闭")

# 创建悬浮控件窗口
class FloatingWidget(QtWidgets.QWidget):
    def __init__(self, assistant: ShopAssistant):
        super().__init__()
        self.assistant = assistant

        # 设置窗口为无边框、置顶、工具窗口
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint |
                            QtCore.Qt.WindowStaysOnTopHint |
                            QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(90, 45)
        self.move(100, 100)

        # 添加右键菜单
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self._press_time = None
        self._drag_pos = None
        self._is_dragging = False
        self.show()

    # 绘制按钮外观
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(5, 5, -5, -5)
        radius = rect.height() / 2

        # 根据启用状态设置颜色和文本
        if self.assistant.enabled:
            bg_color = QtGui.QColor("#00cc44")
            text = "ON"
            knob_x = rect.right() - rect.height()
        else:
            bg_color = QtGui.QColor("#cc0000")
            text = "OFF"
            knob_x = rect.left()

        # 绘制背景和边框
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        pen = QtGui.QPen(QtGui.QColor("black"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        # 绘制文字
        painter.setPen(QtGui.QColor("black"))
        font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        painter.setFont(font)
        text_rect = rect.adjusted(10, 0, -40, 0) if self.assistant.enabled else rect.adjusted(40, 0, -10, 0)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, text)

        # 绘制开关滑块
        knob_rect = QtCore.QRectF(knob_x, rect.top(), rect.height(), rect.height())
        painter.setBrush(QtGui.QColor("#333333"))
        painter.drawEllipse(knob_rect)

    # 鼠标点击事件：判断是否是点击或拖动
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press_time = time.time()
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False

    #如果是拖动，可以移动位置
    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton and self._drag_pos:
            if time.time() - self._press_time > 0.1:
                self.move(event.globalPos() - self._drag_pos)
                self._is_dragging = True

    # 如果是点击，则切换辅助状态
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self._is_dragging:
            self.assistant.toggle()
            self.update()
        self._press_time = None
        self._drag_pos = None
        self._is_dragging = False

    # 右键菜单操作：隐藏或退出
    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        hide_action = menu.addAction("隐藏")
        quit_action = menu.addAction("退出")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == hide_action:
            self.hide()
        elif action == quit_action:
            QtWidgets.qApp.quit()

# 键盘监听器回调函数
def on_press(key, assistant: ShopAssistant, float_ui: FloatingWidget):
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

# 程序入口
if __name__ == "__main__":
    # 点击偏移
    click_offset = (70, 60)

    #模型导入
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)

    model_rel = os.path.join('runs', 'detect', 'train3', 'weights', 'best.pt')
    model_path = os.path.join(base_path, model_rel)
    assistant = ShopAssistant(model_path, click_offset=click_offset)

    # 初始化助手和UI
    assistant = ShopAssistant(model_path, click_offset=click_offset)
    app = QtWidgets.QApplication([])
    float_ui = FloatingWidget(assistant)
    assistant.ui_callback = float_ui.update

    # 启动键盘监听线程
    listener = keyboard.Listener(on_press=lambda key: on_press(key, assistant, float_ui))
    listener.daemon = True
    listener.start()

    # 启动检测线程
    assistant_thread = threading.Thread(target=assistant.run, daemon=True)
    assistant_thread.start()

    # 启动UI主循环
    sys.exit(app.exec_())
