import sys
import time
import logging
import threading
from dataclasses import dataclass
from typing import List, Tuple
import pyautogui
import win32api
import win32con
from pynput import keyboard
from PyQt5 import QtCore, QtGui, QtWidgets
from ultralytics import YOLO
import numpy as np


# 基础分辨率
BASE_WIDTH = 1920
BASE_HEIGHT = 1080

@dataclass
class ShopConfig:
    # 推荐弈子参照识别位置
    recommend_points: List[List[Tuple[int, int]]]
    # 升星参照识别位置
    rise_star_ranges: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    # 推荐弈子参照识别 rgb 模板
    reference_colors: List[Tuple[int, int, int]]
    # rgb 识别允许容差
    color_threshold: int = 50
    # 点击位置偏移
    click_offset: Tuple[int, int] = (0, 0)
    # 检测周期
    poll_interval: float = 1.0
    # 启动延迟
    startup_delay: float = 3.0

# 主逻辑类：商店助手
class ShopAssistant:
    def __init__(self, config: ShopConfig):
        self.model = YOLO(r"D:\code\python_code\autoTft\runs\detect\train3\weights\best.pt")
        self.config = config
        # 是否启用助手
        self.enabled = True
        # UI回调函数
        self.ui_callback = None
        self.enabled = True
        # 日志初始化
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    @staticmethod
    # 计算两颜色差值
    def color_diff(c1, c2):
        return sum(abs(a - b) for a, b in zip(c1, c2))

    # 判断颜色是否匹配
    def is_color_match(self, color, ref):
        return self.color_diff(color, ref) <= self.config.color_threshold

    # 获取截图中指定点颜色
    def get_color(self, screenshot, x, y):
        return screenshot.getpixel((x, y))

    # 判断商店格是否为推荐
    def is_recommended(self, idx, screenshot):
        for pt, ref_col in zip(self.config.recommend_points[idx], self.config.reference_colors):
            if not self.is_color_match(self.get_color(screenshot, *pt), ref_col):
                return False
        return True

    # 判断商店格是否为可升星
    def can_rise_star(self, idx, screenshot):
        (x1, y), (x2, _) = self.config.rise_star_ranges[idx]
        pixels = [screenshot.getpixel((x, y)) for x in range(x1, x2 + 1)]
        for i in range(len(pixels) - 2):
            p1, p2, p3 = pixels[i], pixels[i + 1], pixels[i + 2]
            if p1 == p2 == p3 and p1[0] > 150 and p1[1] > 150:
                return True
        return False

    # 点击指定商店格购买弈子
    def click_slot(self, idx, screenshot):
        pt = self.config.recommend_points[idx][3]
        target = (pt[0] + self.config.click_offset[0], pt[1] + self.config.click_offset[1])
        win32api.SetCursorPos(target)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        time.sleep(0.05)
        logging.info(f"已购买第{idx + 1}个商店格弈子")

    # 单次检测逻辑
    def process_once(self):
        screenshot = pyautogui.screenshot()
        original_pos = win32api.GetCursorPos()
        screenshot_np = np.array(screenshot)[:, :, ::-1]  # RGB to BGR for OpenCV

        results = self.model.predict(source=screenshot_np, conf=0.4, verbose=False)
        detections = results[0].boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
        centers = [(int((x1 + x2) / 2), int((y1 + y2) / 2)) for x1, y1, x2, y2 in detections]

        # 去重：过滤中心点之间距离小于100px的
        filtered = []
        for pt in centers:
            if all(np.linalg.norm(np.array(pt) - np.array(fp)) >= 100 for fp in filtered):
                filtered.append(pt)

        # 执行点击
        for pt in filtered:
            target = (pt[0] + self.config.click_offset[0], pt[1] + self.config.click_offset[1])
            win32api.SetCursorPos(target)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            time.sleep(0.05)
            logging.info(f"点击了检测目标 {pt}")

        if filtered:
            win32api.SetCursorPos(original_pos)

    # 主循环运行函数
    def run(self):
        logging.info(f"三秒后开始识别 {self.config.startup_delay}s...")
        time.sleep(self.config.startup_delay)
        while True:
            if self.enabled:
                self.process_once()
            time.sleep(self.config.poll_interval)

    # 开关启用状态
    def toggle(self):
        self.enabled = not self.enabled
        if self.ui_callback:
            self.ui_callback()
        logging.info("辅助已开启" if self.enabled else "辅助已关闭")

# 缩放工具函数
def scale_points(raw_points, sx, sy):
    return [[(int(x * sx), int(y * sy)) for x, y in row] for row in raw_points]

def scale_ranges(raw_ranges, sx, sy):
    return [((int(x1 * sx), int(y1 * sy)), (int(x2 * sx), int(y2 * sy))) for (x1, y1), (x2, y2) in raw_ranges]

# 悬浮窗口界面
class FloatingWidget(QtWidgets.QWidget):
    def __init__(self, assistant: ShopAssistant):
        super().__init__()
        self.assistant = assistant

        # 设置窗口样式：无边框、总在最前、透明背景
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(90, 45)
        self.move(100, 100)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self._press_time = None
        self._drag_pos = None
        self._is_dragging = False

        self.show()

    # 绘制界面
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 背景
        rect = self.rect().adjusted(5, 5, -5, -5)
        radius = rect.height() / 2

        if self.assistant.enabled:
            bg_color = QtGui.QColor("#00cc44")  # 绿色
            text = "ON"
            knob_pos = rect.right() - rect.height()
        else:
            bg_color = QtGui.QColor("#cc0000")  # 红色
            text = "OFF"
            knob_pos = rect.left()

        # 绘制圆角矩形背景
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # 绘制圆角矩形边框（黑色）
        pen = QtGui.QPen(QtGui.QColor("black"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        # 设置文字颜色和字体
        painter.setPen(QtCore.Qt.white)
        font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        painter.setFont(font)

        # 文字绘制
        painter.setPen(QtCore.Qt.black)
        font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        painter.setFont(font)
        if self.assistant.enabled:
            text_rect = rect.adjusted(10, 0, -40, 0)  # 文字偏右
        else:
            text_rect = rect.adjusted(40, 0, -10, 0)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, text)

        # 绘制滑块
        knob_rect = QtCore.QRectF(knob_pos, rect.top(), rect.height(), rect.height())
        knob_color = QtGui.QColor("#333333")
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)

    #辅助拖动
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press_time = time.time()
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False

    #长按拖动
    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self._drag_pos:
            if time.time() - self._press_time > 0.1:
                self.move(event.globalPos() - self._drag_pos)
                self._is_dragging = True

    # 单击切换启用状态
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self._is_dragging:
            self.assistant.toggle()
            self.update()
        self._press_time = None
        self._drag_pos = None
        self._is_dragging = False

    # 右键菜单
    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        hide_action = menu.addAction("隐藏")
        quit_action = menu.addAction("退出")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == hide_action:
            self.hide()
        elif action == quit_action:
            QtWidgets.qApp.quit()

    def update_status(self):
        self.update()


def on_press(key, assistant: ShopAssistant, float_ui: FloatingWidget):
    try:
        # 按 "d" 检测一次
        if hasattr(key, 'char') and key.char == 'd' and assistant.enabled:
            logging.info("d牌已检测")
            assistant.process_once()

        # 使用功能键 f1 和 f2
        elif key == keyboard.Key.f1:
            assistant.toggle()  # 切换助手开启/关闭
            logging.info("助手已切换")

        elif key == keyboard.Key.f2:
            if float_ui.isVisible():
                float_ui.hide()  # 如果窗口已经显示，则隐藏
                logging.info("窗口已隐藏")
            else:
                float_ui.show()  # 如果窗口没有显示，则显示
                logging.info("窗口已显示")

    except AttributeError:
        pass

def main():
    raw_recommend_points = [
        [(494, 929), (509, 929), (509, 946), (493, 948), (501, 936)],
        [(694, 929), (709, 929), (709, 946), (693, 948), (702, 936)],
        [(894, 929), (909, 929), (909, 946), (894, 948), (902, 936)],
        [(1096, 929), (1109, 929), (1109, 946), (1096, 948), (1105, 935)],
        [(1302, 929), (1309, 929), (1309, 946), (1297, 948), (1306, 939)],
    ]
    raw_rise_star_ranges = [
        ((494, 932), (518, 932)),
        ((695, 932), (719, 932)),
        ((896, 932), (920, 932)),
        ((1098, 932), (1121, 932)),
        ((1299, 932), (1323, 932)),
    ]
    raw_click_offset = (70, 60)
    reference_colors = [(55, 138, 90), (55, 138, 90), (60, 99, 79), (60, 96, 77), (255, 238, 198)]

    current_w, current_h = pyautogui.size()
    sx = current_w / BASE_WIDTH
    sy = current_h / BASE_HEIGHT

    recommend_points = scale_points(raw_recommend_points, sx, sy)
    rise_star_ranges = scale_ranges(raw_rise_star_ranges, sx, sy)
    click_offset = (int(raw_click_offset[0] * sx), int(raw_click_offset[1] * sy))

    config = ShopConfig(
        recommend_points=recommend_points,
        rise_star_ranges=rise_star_ranges,
        reference_colors=reference_colors,
        click_offset=click_offset
    )
    assistant = ShopAssistant(config)

    app = QtWidgets.QApplication([])
    float_ui = FloatingWidget(assistant)
    assistant.ui_callback = float_ui.update
    float_ui.show()

    listener = keyboard.Listener(on_press=lambda key: on_press(key, assistant, float_ui))
    listener.daemon = True
    listener.start()

    assistant_thread = threading.Thread(target=assistant.run, daemon=True)
    assistant_thread.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()