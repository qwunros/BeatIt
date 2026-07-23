"""
BeatIT 主界面

基于 tkinter 构建，整合所有功能：
- 录制控制（开始/停止/清空）
- 实时简谱显示
- BPM 自动检测与手动调节
- 导出功能（PNG/MIDI/TXT）
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading

from core.recorder import InputRecorder
from core.bpm_detector import detect_bpm_sliding, manual_adjust
from core.quantizer import quantize_interval, format_notation, format_notation_simple
from core.exporter import export_midi, export_image, export_text, PERCUSSION_MAP
from ui.widgets import NotationCanvas


# 量化力度预设
SNAP_PRESETS = {
    '宽松': 0.3,
    '适中': 0.6,
    '严格': 0.85,
    '完全': 1.0,
}


class BeatITApp(tk.Tk):
    """BeatIT 主应用窗口"""

    def __init__(self):
        super().__init__()

        self.title('BeatIT — 点击节奏转简谱')
        self.geometry('800x650')
        self.minsize(650, 500)
        self.configure(bg='#FAFAFA')

        # 核心组件
        self.recorder = InputRecorder()

        # 状态
        self._current_bpm = 120.0
        self._snap_strength = 0.6
        self._time_sig = (4, 4)
        self._midi_instrument = 'Closed Hi-Hat'
        self._input_sources = {'mouse': True, 'keyboard': True}
        self._bpm_multiplier = 1.0  # 当前 BPM 倍率

        # 缓存的量化音符
        self._quantized_notes = []  # list[(ratio, symbol)]
        self._raw_intervals = []

        # 选择导出格式用的变量
        self._export_format = tk.StringVar(value='png')

        # 构建 UI
        self._build_ui()

        # 启动定时轮询
        self._poll_interval = 100  # ms
        self._poll_events()

        # 窗口关闭处理
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ──────────────── UI 构建 ────────────────

    def _build_ui(self):
        """构建全部 UI 组件"""
        self._build_control_bar()
        self._build_notation_area()
        self._build_status_bar()
        self._build_settings_panel()

    def _build_control_bar(self):
        """顶部控制栏"""
        ctrl_frame = tk.Frame(self, bg='#FAFAFA', padx=10, pady=8)
        ctrl_frame.pack(fill='x')

        # 录制控制
        self.btn_start = tk.Button(
            ctrl_frame, text='▶ 开始录制',
            command=self._start_recording,
            bg='#4CAF50', fg='white', font=('Microsoft YaHei', 10, 'bold'),
            padx=12, pady=4, relief='flat', cursor='hand2'
        )
        self.btn_start.pack(side='left', padx=(0, 5))

        self.btn_stop = tk.Button(
            ctrl_frame, text='■ 停止录制',
            command=self._stop_recording,
            bg='#F44336', fg='white', font=('Microsoft YaHei', 10, 'bold'),
            padx=12, pady=4, relief='flat', state='disabled', cursor='hand2'
        )
        self.btn_stop.pack(side='left', padx=5)

        self.btn_clear = tk.Button(
            ctrl_frame, text='✕ 清空',
            command=self._clear_all,
            bg='#757575', fg='white', font=('Microsoft YaHei', 9),
            padx=8, pady=4, relief='flat', cursor='hand2'
        )
        self.btn_clear.pack(side='left', padx=5)

        # 状态指示器
        self.lbl_status = tk.Label(
            ctrl_frame, text='● 已停止',
            fg='#757575', bg='#FAFAFA',
            font=('Microsoft YaHei', 9)
        )
        self.lbl_status.pack(side='left', padx=15)

        # 事件计数
        self.lbl_count = tk.Label(
            ctrl_frame, text='点击: 0',
            fg='#616161', bg='#FAFAFA',
            font=('Microsoft YaHei', 9)
        )
        self.lbl_count.pack(side='right', padx=5)

        self.lbl_duration = tk.Label(
            ctrl_frame, text='时长: 0.0s',
            fg='#616161', bg='#FAFAFA',
            font=('Microsoft YaHei', 9)
        )
        self.lbl_duration.pack(side='right', padx=15)

    def _build_notation_area(self):
        """简谱显示区域"""
        # 使用 PanedWindow 以便后续扩展
        notation_frame = tk.Frame(self, bg='#FFFDE7', padx=5, pady=5)
        notation_frame.pack(fill='both', expand=True, padx=10, pady=(0, 5))

        # 带滚动条的画布
        scrollbar = tk.Scrollbar(notation_frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')

        self.canvas = NotationCanvas(
            notation_frame,
            yscrollcommand=scrollbar.set,
            height=250
        )
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.canvas.yview)

        # 让 Canvas 支持鼠标滚轮滚动
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        self.canvas.bind_all('<MouseWheel>', _on_mousewheel)

    def _build_status_bar(self):
        """BPM 状态栏 + 手动调节"""
        status_frame = tk.Frame(self, bg='#FAFAFA', padx=10, pady=5)
        status_frame.pack(fill='x')

        # BPM 显示
        tk.Label(
            status_frame, text='BPM:',
            font=('Microsoft YaHei', 10), bg='#FAFAFA', fg='#424242'
        ).pack(side='left')

        self.lbl_bpm = tk.Label(
            status_frame, text='120',
            font=('Microsoft YaHei', 14, 'bold'),
            bg='#FAFAFA', fg='#1A237E', width=5
        )
        self.lbl_bpm.pack(side='left')

        # BPM 手动调节按钮 (2的幂次)
        bpm_adjust_frame = tk.Frame(status_frame, bg='#FAFAFA')
        bpm_adjust_frame.pack(side='left', padx=10)

        bpm_buttons = [
            ('×½', 0.5), ('×1', 1.0), ('×2', 2.0),
            ('×4', 4.0), ('×8', 8.0),
        ]
        for label, mult in bpm_buttons:
            btn = tk.Button(
                bpm_adjust_frame, text=label,
                command=lambda m=mult: self._adjust_bpm(m),
                font=('Microsoft YaHei', 8),
                bg='#E8EAF6', fg='#283593',
                padx=6, pady=1, relief='flat', cursor='hand2',
                width=3
            )
            btn.pack(side='left', padx=2)

        # 置信度
        self.lbl_confidence = tk.Label(
            status_frame, text='',
            font=('Microsoft YaHei', 8), bg='#FAFAFA', fg='#9E9E9E'
        )
        self.lbl_confidence.pack(side='left', padx=10)

    def _build_settings_panel(self):
        """底部设置面板"""
        settings_frame = tk.Frame(self, bg='#F5F5F5', padx=12, pady=8)
        settings_frame.pack(fill='x', side='bottom')

        # --- 第一行: 量化力度 + 节拍 + 输入源 ---
        row1 = tk.Frame(settings_frame, bg='#F5F5F5')
        row1.pack(fill='x', pady=(0, 5))

        # 量化力度
        tk.Label(
            row1, text='量化力度:', bg='#F5F5F5',
            font=('Microsoft YaHei', 9)
        ).pack(side='left')

        self.snap_var = tk.DoubleVar(value=0.6)
        snap_scale = tk.Scale(
            row1, from_=0, to=1.0, resolution=0.05,
            orient='horizontal', variable=self.snap_var,
            length=120, bg='#F5F5F5', highlightthickness=0,
            font=('Microsoft YaHei', 7), showvalue=False
        )
        snap_scale.pack(side='left', padx=(0, 5))

        self.lbl_snap_value = tk.Label(
            row1, text='适中', bg='#F5F5F5',
            font=('Microsoft YaHei', 9), fg='#616161', width=4
        )
        self.lbl_snap_value.pack(side='left', padx=(0, 10))

        # 量化力度预设按钮
        for name, val in SNAP_PRESETS.items():
            btn = tk.Button(
                row1, text=name,
                command=lambda v=val, n=name: self._set_snap(v, n),
                font=('Microsoft YaHei', 7),
                bg='#E0E0E0', fg='#424242',
                padx=4, pady=0, relief='flat', cursor='hand2'
            )
            btn.pack(side='left', padx=1)

        # 节拍
        tk.Label(
            row1, text='  节拍:', bg='#F5F5F5',
            font=('Microsoft YaHei', 9)
        ).pack(side='left', padx=(15, 0))

        self.time_sig_var = tk.StringVar(value='4/4')
        time_sig_combo = ttk.Combobox(
            row1, textvariable=self.time_sig_var,
            values=['2/2', '2/4', '3/4', '4/4', '6/8'],
            width=5, state='readonly',
            font=('Microsoft YaHei', 9)
        )
        time_sig_combo.pack(side='left', padx=(0, 10))
        time_sig_combo.bind('<<ComboboxSelected>>', self._on_time_sig_change)

        # 输入源
        tk.Label(
            row1, text='  输入:', bg='#F5F5F5',
            font=('Microsoft YaHei', 9)
        ).pack(side='left')

        self.mouse_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row1, text='鼠标', variable=self.mouse_var,
            bg='#F5F5F5', font=('Microsoft YaHei', 9),
            command=self._update_input_sources
        ).pack(side='left')

        self.keyboard_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row1, text='键盘', variable=self.keyboard_var,
            bg='#F5F5F5', font=('Microsoft YaHei', 9),
            command=self._update_input_sources
        ).pack(side='left')

        # --- 第二行: 导出 ---
        row2 = tk.Frame(settings_frame, bg='#F5F5F5')
        row2.pack(fill='x')

        # MIDI 乐器选择
        tk.Label(
            row2, text='MIDI 音色:', bg='#F5F5F5',
            font=('Microsoft YaHei', 9)
        ).pack(side='left')

        self.instrument_var = tk.StringVar(value='Closed Hi-Hat')
        instr_combo = ttk.Combobox(
            row2, textvariable=self.instrument_var,
            values=list(PERCUSSION_MAP.keys()),
            width=15, state='readonly',
            font=('Microsoft YaHei', 8)
        )
        instr_combo.pack(side='left', padx=(0, 10))

        # 导出按钮
        tk.Button(
            row2, text='📷 导出 PNG',
            command=self._export_png,
            bg='#FF8F00', fg='white',
            font=('Microsoft YaHei', 9, 'bold'),
            padx=8, pady=2, relief='flat', cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            row2, text='🎵 导出 MIDI',
            command=self._export_midi,
            bg='#1565C0', fg='white',
            font=('Microsoft YaHei', 9, 'bold'),
            padx=8, pady=2, relief='flat', cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            row2, text='📄 导出 TXT',
            command=self._export_txt,
            bg='#616161', fg='white',
            font=('Microsoft YaHei', 9, 'bold'),
            padx=8, pady=2, relief='flat', cursor='hand2'
        ).pack(side='left', padx=2)

    # ──────────────── 核心逻辑 ────────────────

    def _start_recording(self):
        """开始录制"""
        self._quantized_notes = []
        self._raw_intervals = []
        self._bpm_multiplier = 1.0

        self.recorder.start()

        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.lbl_status.config(text='● 录制中', fg='#4CAF50')
        self.canvas.update_display('🎯 录制中...', '等待输入...',
                                   '点击鼠标或按键盘任意键开始')

    def _stop_recording(self):
        """停止录制"""
        self.recorder.stop()

        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.lbl_status.config(text='● 已停止', fg='#757575')

        # 最终分析
        self._analyze_and_update()

    def _clear_all(self):
        """清空所有数据"""
        if self.recorder.is_running:
            self.recorder.stop()
            self.btn_start.config(state='normal')
            self.btn_stop.config(state='disabled')
            self.lbl_status.config(text='● 已停止', fg='#757575')

        # 清空数据
        self.recorder.events.clear()
        self._quantized_notes = []
        self._raw_intervals = []
        self._current_bpm = 120.0
        self._bpm_multiplier = 1.0

        self.lbl_bpm.config(text='120')
        self.lbl_confidence.config(text='')
        self.lbl_count.config(text='点击: 0')
        self.lbl_duration.config(text='时长: 0.0s')

        self.canvas._draw_welcome()

    def _poll_events(self):
        """定时轮询事件队列（每 100ms）"""
        if self.recorder.is_running:
            new_events = self.recorder.poll_events()

            if new_events:
                # 更新计数
                count = self.recorder.event_count
                duration = self.recorder.get_duration()
                self.lbl_count.config(text=f'点击: {count}')
                self.lbl_duration.config(text=f'时长: {duration:.1f}s')

                # 获取间隔并检测 BPM
                intervals = self.recorder.get_intervals()
                if len(intervals) >= 2:
                    self._raw_intervals = intervals

                    # 滑动窗口 BPM 检测
                    bpm, confidence = detect_bpm_sliding(intervals, window_size=20)
                    if confidence > 0:
                        self._current_bpm = bpm
                        display_bpm = round(bpm * self._bpm_multiplier)
                        self.lbl_bpm.config(text=str(display_bpm))
                        self.lbl_confidence.config(
                            text=f'置信度: {confidence:.0%}')

                    # 量化所有事件并更新显示
                    self._quantize_and_display()

        # 继续轮询
        self.after(self._poll_interval, self._poll_events)

    def _quantize_and_display(self):
        """量化所有间隔并更新简谱显示"""
        if len(self._raw_intervals) < 2:
            return

        effective_bpm = self._current_bpm * self._bpm_multiplier

        # 量化每个间隔
        self._quantized_notes = []
        for ioi in self._raw_intervals:
            _, closest_ratio, symbol = quantize_interval(
                ioi, effective_bpm, self._snap_strength
            )
            self._quantized_notes.append((closest_ratio, symbol))

        # 格式化显示
        notation = format_notation(
            self._quantized_notes, effective_bpm, self._time_sig
        )

        # 提取头部和主体
        lines = notation.split('\n', 1)
        header = lines[0] if lines else ''
        body = lines[1] if len(lines) > 1 else ''

        # 附加信息
        info = (f'已录制 {self.recorder.event_count} 次点击 | '
                f'共 {len(self._quantized_notes)} 个音符 | '
                f'量化力度: {self._snap_strength:.0%}')

        self.canvas.update_display(header, body, info)

    def _analyze_and_update(self):
        """停止后进行最终分析"""
        if len(self._raw_intervals) < 2:
            return

        effective_bpm = self._current_bpm * self._bpm_multiplier

        notation = format_notation(
            self._quantized_notes, effective_bpm, self._time_sig
        )
        lines = notation.split('\n', 1)
        header = lines[0] if lines else ''
        body = lines[1] if len(lines) > 1 else ''

        info = (f'录制完成: {self.recorder.event_count} 次点击 | '
                f'{len(self._quantized_notes)} 个音符 | '
                f'总时长: {self.recorder.get_duration():.1f}s')

        self.canvas.update_display(header, body, info)

    # ──────────────── 用户操作回调 ────────────────

    def _adjust_bpm(self, multiplier):
        """手动调节 BPM 倍率"""
        self._bpm_multiplier = multiplier
        effective_bpm = round(self._current_bpm * multiplier)
        self.lbl_bpm.config(text=str(effective_bpm))

        # 重新渲染
        self._quantize_and_display()

    def _set_snap(self, value, name):
        """设置量化力度"""
        self._snap_strength = value
        self.snap_var.set(value)
        self.lbl_snap_value.config(text=name)
        self._quantize_and_display()

    def _on_time_sig_change(self, event=None):
        """节拍变化"""
        sig = self.time_sig_var.get()
        parts = sig.split('/')
        if len(parts) == 2:
            try:
                self._time_sig = (int(parts[0]), int(parts[1]))
                self._quantize_and_display()
            except ValueError:
                pass

    def _update_input_sources(self):
        """更新输入源过滤"""
        self._input_sources['mouse'] = self.mouse_var.get()
        self._input_sources['keyboard'] = self.keyboard_var.get()
        # TODO: 可在 recorder 中实现过滤逻辑

    # ──────────────── 导出功能 ────────────────

    def _export_png(self):
        """导出为 PNG 图片"""
        if not self._quantized_notes:
            messagebox.showwarning('提示', '没有可导出的节奏数据。\n请先录制一些节奏。')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出为图片',
            defaultextension='.png',
            filetypes=[('PNG 图片', '*.png'), ('所有文件', '*.*')]
        )
        if not filepath:
            return

        try:
            # 获取当前显示的简谱文本
            effective_bpm = self._current_bpm * self._bpm_multiplier
            notation = format_notation(
                self._quantized_notes, effective_bpm, self._time_sig
            )
            export_image(notation, filepath)
            messagebox.showinfo('导出成功', f'图片已保存到:\n{filepath}')
        except Exception as e:
            messagebox.showerror('导出失败', f'导出图片时出错:\n{str(e)}')

    def _export_midi(self):
        """导出为 MIDI 文件"""
        if len(self.recorder.events) < 2:
            messagebox.showwarning('提示', '没有可导出的节奏数据。\n请先录制一些节奏。')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出为 MIDI',
            defaultextension='.mid',
            filetypes=[('MIDI 文件', '*.mid'), ('所有文件', '*.*')]
        )
        if not filepath:
            return

        try:
            effective_bpm = self._current_bpm * self._bpm_multiplier
            instrument = self.instrument_var.get()
            export_midi(
                self.recorder.events,
                effective_bpm,
                filepath,
                instrument_name=instrument
            )
            messagebox.showinfo('导出成功', f'MIDI 文件已保存到:\n{filepath}')
        except Exception as e:
            messagebox.showerror('导出失败', f'导出 MIDI 时出错:\n{str(e)}')

    def _export_txt(self):
        """导出为 TXT 文本"""
        if not self._quantized_notes:
            messagebox.showwarning('提示', '没有可导出的节奏数据。\n请先录制一些节奏。')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出为文本',
            defaultextension='.txt',
            filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')]
        )
        if not filepath:
            return

        try:
            effective_bpm = self._current_bpm * self._bpm_multiplier
            notation = format_notation(
                self._quantized_notes, effective_bpm, self._time_sig
            )
            # 添加附加信息
            full_text = (
                f"BeatIT 节奏转简谱\n"
                f"{'=' * 40}\n"
                f"BPM: {effective_bpm:.0f}\n"
                f"节拍: {self._time_sig[0]}/{self._time_sig[1]}\n"
                f"量化力度: {self._snap_strength:.0%}\n"
                f"点击次数: {self.recorder.event_count}\n"
                f"录制时长: {self.recorder.get_duration():.1f}s\n"
                f"{'=' * 40}\n\n"
                f"{notation}\n"
            )
            export_text(full_text, filepath)
            messagebox.showinfo('导出成功', f'文本文件已保存到:\n{filepath}')
        except Exception as e:
            messagebox.showerror('导出失败', f'导出文本时出错:\n{str(e)}')

    def _on_close(self):
        """窗口关闭处理"""
        if self.recorder.is_running:
            self.recorder.stop()
        self.destroy()


def run_app():
    """启动应用"""
    app = BeatITApp()
    app.mainloop()
