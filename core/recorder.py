"""
输入事件采集模块 - InputRecorder

使用 pynput 全局监听鼠标点击和键盘按键，
在后台线程运行，通过 queue.Queue 向主线程安全传递事件。
"""
import time
import threading
from queue import Queue, Empty
from pynput import mouse, keyboard


class InputRecorder:
    """全局输入事件采集器"""

    def __init__(self):
        self._mouse_listener = None
        self._keyboard_listener = None
        self._thread = None
        self._running = False

        # 线程安全的事件队列
        # 每条事件: (timestamp, event_type)
        # event_type: 'mouse' | 'keyboard'
        self.event_queue = Queue()

        # 完整事件列表（用于最终导出和分析）
        self.events = []

        self._start_time = 0.0

    def _on_click(self, x, y, button, pressed):
        """鼠标点击回调"""
        if pressed and self._running:
            ts = time.perf_counter()
            self.event_queue.put((ts, 'mouse'))

    def _on_press(self, key):
        """键盘按键回调"""
        if self._running:
            ts = time.perf_counter()
            self.event_queue.put((ts, 'keyboard'))

    def start(self):
        """启动监听"""
        if self._running:
            return

        self._running = True
        self.events.clear()
        # 清空队列中的旧事件
        while True:
            try:
                self.event_queue.get_nowait()
            except Empty:
                break

        self._start_time = time.perf_counter()

        # 启动鼠标监听
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()

        # 启动键盘监听
        self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
        self._keyboard_listener.start()

    def stop(self):
        """停止监听"""
        self._running = False

        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def poll_events(self):
        """轮询获取新事件（非阻塞，供主线程调用）

        返回: list[(timestamp, event_type)]
        """
        new_events = []
        while True:
            try:
                event = self.event_queue.get_nowait()
                new_events.append(event)
                self.events.append(event)
            except Empty:
                break
        return new_events

    def get_intervals(self):
        """获取所有击键间隔 (IOI) 列表

        返回: list[float] — 相邻事件的时间间隔（秒）
        """
        if len(self.events) < 2:
            return []
        timestamps = [e[0] for e in self.events]
        return [timestamps[i + 1] - timestamps[i]
                for i in range(len(timestamps) - 1)]

    def get_duration(self):
        """获取录制总时长（秒）"""
        if len(self.events) < 2:
            return 0.0
        return self.events[-1][0] - self.events[0][0]

    @property
    def is_running(self):
        return self._running

    @property
    def event_count(self):
        return len(self.events)
