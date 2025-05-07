import time
import logging
import pyautogui
from ultralytics import YOLO
import numpy as np
import win32api
import win32con
import win32gui
import cv2


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
        #self._local = threading.local()
        self.class_names = {
            0: "推荐",
            1: "升星",
            2: "粘液",
        }
        #启用点击类型
        self.target_classes = {0, 1, 2}

        # 日志初始化
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )


    def toggle_target_class(self, class_id: int):
        """切换 class_id 是否被选中"""
        if class_id in self.target_classes:
            self.target_classes.remove(class_id)
        else:
            self.target_classes.add(class_id)
        logging.info(f"当前可点击类别：{sorted(self.target_classes)}")

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
        if img0 is None:
            logging.info("图像为空")
            return
        img = cv2.resize(img0, (self.REF_W, self.REF_H))
        results = self.model.predict(source=img, conf=0.4, verbose=False)

        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)


        # 反算回原始窗口区域中的坐标
        scale_x = w0 / self.REF_W
        scale_y = h0 / self.REF_H
        centers = []
        for (x1, y1, x2, y2), cls in zip(xyxy, cls_ids):
            if cls not in self.target_classes:
                continue
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