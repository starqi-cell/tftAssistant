from PyQt5 import QtWidgets, QtGui, QtCore
import time


# 创建悬浮控件窗口
class FloatingWidget(QtWidgets.QWidget):
    def __init__(self, assistant):
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
        # 1) 添加 class_id 选择项，做成可勾选
        for cls, name in self.assistant.class_names.items():
            action = QtWidgets.QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(cls in self.assistant.target_classes)
            action.triggered.connect(lambda checked, c=cls: self.on_toggle_class(c))
            menu.addAction(action)

        menu.addSeparator()
        # 2) 隐藏窗口
        hide_action = menu.addAction("隐藏")
        # 3) 退出程序
        quit_action = menu.addAction("退出")

        action = menu.exec_(self.mapToGlobal(pos))
        if action == hide_action:
            self.hide()
        elif action == quit_action:
            QtWidgets.qApp.quit()
    def on_toggle_class(self, cls: int):
        """响应菜单勾选，切换类别并刷新按钮状态"""
        self.assistant.toggle_target_class(cls)
        self.update()