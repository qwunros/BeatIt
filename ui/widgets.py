"""
自定义 GUI 组件

NotationCanvas — 基于 tkinter.Canvas 的简谱渲染组件
支持实时追加音符和图片导出
"""
import tkinter as tk
from tkinter import font as tkfont


class NotationCanvas(tk.Canvas):
    """简谱渲染画布"""

    # 颜色方案
    BG_COLOR = '#FFFDE7'       # 米黄色纸张底色
    TEXT_COLOR = '#1A1A1A'     # 深色文字
    MEASURE_LINE_COLOR = '#BDBDBD'  # 浅灰色小节线
    BAR_LINE_COLOR = '#757575'      # 深灰色终止线
    HEADER_COLOR = '#5D4037'        # 棕色标题

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

        self.configure(
            bg=self.BG_COLOR,
            highlightthickness=1,
            highlightbackground='#E0E0E0',
        )

        # 字体
        self._notation_font = tkfont.Font(family='Consolas', size=16)
        self._header_font = tkfont.Font(family='Microsoft YaHei', size=12)
        self._info_font = tkfont.Font(family='Microsoft YaHei', size=10)

        # 布局参数
        self._x_margin = 20
        self._y_start = 20
        self._line_height = 35
        self._header_height = 30

        # 存储绘制的文本和位置
        self._current_y = self._y_start
        self._notation_lines = []

        # 初始化显示欢迎信息
        self._draw_welcome()

    def _draw_welcome(self):
        """绘制欢迎信息"""
        self.delete('all')
        self._current_y = self._y_start
        self._notation_lines = []

        self.create_text(
            self._x_margin, self._current_y,
            text='🎵 BeatIT — 点击节奏转简谱工具',
            anchor='nw', font=self._header_font,
            fill=self.HEADER_COLOR
        )
        self._current_y += self._header_height

        self.create_text(
            self._x_margin, self._current_y,
            text='点击「开始录制」后，用鼠标或键盘敲击节奏...',
            anchor='nw', font=self._info_font,
            fill='#9E9E9E'
        )
        self._current_y += self._line_height

        instr_text = (
            '简谱说明:\n'
            '  X = 四分  |  X̲ = 八分  |  X̲̲ = 十六分\n'
            '  X- = 二分  |  X--- = 全音符  |  X· = 附点\n'
            '  0 = 休止符'
        )
        self.create_text(
            self._x_margin, self._current_y,
            text=instr_text, anchor='nw', font=self._info_font,
            fill='#757575'
        )

    def update_display(self, header_text, notation_text, info_text=''):
        """更新简谱显示

        Args:
            header_text: str — 顶部信息（节拍、BPM）
            notation_text: str — 简谱主体
            info_text: str — 额外信息
        """
        self.delete('all')
        self._current_y = self._y_start
        self._notation_lines = []

        # 绘制头部
        self.create_text(
            self._x_margin, self._current_y,
            text=header_text,
            anchor='nw', font=self._header_font,
            fill=self.HEADER_COLOR
        )
        self._current_y += self._header_height

        # 分割简谱文本为行
        lines = notation_text.split('\n')

        for line in lines:
            if not line.strip():
                self._current_y += 10
                continue

            # 检查是否包含小节线标记
            if '|' in line or '||' in line:
                self._draw_notation_line(line)
            else:
                self.create_text(
                    self._x_margin, self._current_y,
                    text=line, anchor='nw',
                    font=self._notation_font,
                    fill=self.TEXT_COLOR
                )
                self._current_y += self._line_height

        # 绘制额外信息
        if info_text:
            self._current_y += 10
            self.create_text(
                self._x_margin, self._current_y,
                text=info_text, anchor='nw',
                font=self._info_font,
                fill='#616161'
            )

        # 更新滚动区域
        self.configure(scrollregion=self.bbox('all'))

    def _draw_notation_line(self, line):
        """绘制一行简谱，超出画布宽度时自动换行"""
        # 计算可用宽度
        max_width = self.winfo_width() - self._x_margin * 2
        if max_width < 100:
            max_width = 600  # 画布尚未完成布局时的回退值

        gap = self._notation_font.measure(' ') * 1.5  # 音符间距

        # 解析小节: 将 '|' 前后的内容拆分为 (文本, 小节线类型)
        # 类型: None=无, 'single'=单线, 'double'=双线
        has_double_bar = '||' in line
        raw_parts = line.replace('||', '|').split('|')
        segments = []  # list of (text_or_None, bar_type_or_None)

        for i, part in enumerate(raw_parts):
            part = part.strip()
            if i == len(raw_parts) - 1:
                # 最后一段后面没有小节线
                if part:
                    segments.append((part, None))
            elif has_double_bar and i == len(raw_parts) - 2:
                # 双小节线
                if part:
                    segments.append((part, 'double'))
                else:
                    segments.append((None, 'double'))
            else:
                # 单小节线
                if part:
                    segments.append((part, 'single'))

        # 逐段绘制，超出宽度则换行
        x = self._x_margin
        y = self._current_y
        line_start_x = self._x_margin

        def _start_new_line():
            """换到新的一行"""
            nonlocal x, y
            self._current_y += self._line_height
            y = self._current_y
            x = line_start_x

        for text, bar_type in segments:
            # 计算本段文本宽度 + 小节线宽度
            seg_width = 0
            if text:
                seg_width += self._notation_font.measure(text) + gap
            if bar_type:
                bar_symbol = '‖' if bar_type == 'double' else '|'
                seg_width += self._notation_font.measure(bar_symbol) + gap

            # 如果当前行放不下，换行（至少保证每段从行首开始）
            if x > line_start_x and x + seg_width > self._x_margin + max_width:
                _start_new_line()

            # 绘制音符文本
            if text:
                self.create_text(
                    x, y, text=text, anchor='nw',
                    font=self._notation_font,
                    fill=self.TEXT_COLOR
                )
                x += self._notation_font.measure(text) + gap

            # 绘制小节线
            if bar_type:
                bar_symbol = '‖' if bar_type == 'double' else '|'
                bar_color = self.BAR_LINE_COLOR if bar_type == 'double' else self.MEASURE_LINE_COLOR
                self.create_text(
                    x, y, text=bar_symbol, anchor='nw',
                    font=self._notation_font, fill=bar_color
                )
                x += self._notation_font.measure(bar_symbol) + gap

        self._current_y += self._line_height
