"""
导出模块 — 支持 MIDI、图片(PNG)、文本(TXT) 三种格式
"""
import os
import numpy as np
from midiutil import MIDIFile
from PIL import Image, ImageDraw, ImageFont


# MIDI 打击乐音色映射 (GM Standard)
PERCUSSION_MAP = {
    'Closed Hi-Hat': 42,
    'Open Hi-Hat': 46,
    'Kick': 36,
    'Snare': 38,
    'Tom Low': 41,
    'Tom Mid': 45,
    'Tom High': 48,
    'Crash': 49,
    'Ride': 51,
    'Clap': 39,
}


def export_midi(events, bpm, filepath, instrument_name='Closed Hi-Hat',
                velocity=100, duration_beats=0.25):
    """导出为 MIDI 文件

    Args:
        events: list[(timestamp, event_type)] — 事件列表
        bpm: float — BPM
        filepath: str — 输出文件路径
        instrument_name: str — 打击乐器名称 (见 PERCUSSION_MAP)
        velocity: int — 力度 (0-127)
        duration_beats: float — 每个音符的时长（拍）
    """
    if len(events) < 2:
        raise ValueError("事件数量不足，无法导出 MIDI")

    # 获取 MIDI 音符号
    note = PERCUSSION_MAP.get(instrument_name, 42)

    # 创建 MIDI 文件 (1 轨)
    midi = MIDIFile(1)
    track = 0
    midi.addTempo(track, 0, bpm)

    channel = 9  # MIDI 打击乐通道 (通道 10, index 9)

    start_time = events[0][0]
    quarter_dur = 60.0 / bpm

    for i, (timestamp, event_type) in enumerate(events):
        # 将时间戳转换为拍子数
        time_in_beats = (timestamp - start_time) / quarter_dur
        midi.addNote(track, channel, note, time_in_beats, duration_beats, velocity)

    with open(filepath, 'wb') as f:
        midi.writeFile(f)


def export_image(notation_text, filepath, font_size=20, padding=30):
    """将简谱文本导出为 PNG 图片

    Args:
        notation_text: str — 完整的简谱文本
        filepath: str — 输出文件路径 (.png)
        font_size: int — 字体大小
        padding: int — 内边距
    """
    lines = notation_text.split('\n')

    # 计算图片尺寸
    line_height = font_size * 1.8

    # 尝试加载支持 Unicode 的字体
    font = _get_font(font_size)

    # 先估算尺寸
    temp_img = Image.new('RGB', (1, 1), 'white')
    temp_draw = ImageDraw.Draw(temp_img)

    max_width = padding * 2
    total_height = padding * 2

    for line in lines:
        if line.strip():
            bbox = temp_draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            max_width = max(max_width, line_width + padding * 2)
        total_height += line_height

    total_height = max(total_height, padding * 2 + line_height)

    # 创建图片
    img = Image.new('RGB', (max_width, total_height), 'white')
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        if line.strip():
            draw.text((padding, y), line, fill='black', font=font)
        y += line_height

    img.save(filepath, 'PNG')


def _get_font(font_size):
    """尝试获取可用的支持 Unicode 字体"""
    font_paths = [
        # Windows 中文字体
        'C:/Windows/Fonts/msyh.ttc',       # 微软雅黑
        'C:/Windows/Fonts/simsun.ttc',     # 宋体
        'C:/Windows/Fonts/simhei.ttf',     # 黑体
        'C:/Windows/Fonts/arial.ttf',      # Arial
        # macOS
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        # Linux
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue

    # 回退到默认字体
    return ImageFont.load_default()


def export_text(notation_text, filepath):
    """导出为纯文本文件

    Args:
        notation_text: str — 简谱文本
        filepath: str — 输出文件路径 (.txt)
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(notation_text)
