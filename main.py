"""
BeatIT — 点击节奏转简谱工具

将鼠标或键盘点击的节奏实时转换为简谱节奏谱，
自动检测 BPM，支持手动调节，可导出为 PNG/MIDI/TXT。

使用方式:
    python main.py

依赖:
    pip install pynput numpy midiutil Pillow
"""
import sys
import os

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import run_app


def main():
    """程序入口"""
    try:
        run_app()
    except KeyboardInterrupt:
        print('\n程序已退出')
    except Exception as e:
        print(f'启动失败: {e}')
        import traceback
        traceback.print_exc()
        input('\n按 Enter 键退出...')


if __name__ == '__main__':
    main()
