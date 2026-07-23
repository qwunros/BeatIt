"""
量化与简谱生成模块

把连续时间间隔映射到标准音符时值，并渲染为简谱节奏字符串。

简谱节奏记法 (打击乐用 X)：
  - X--- — 全音符 (4 个四分音符)
  - X-   — 二分音符 (2 个四分音符)
  - X    — 四分音符
  - X̲   — 八分音符 (1/2 个四分音符)
  - X̲̲  — 十六分音符 (1/4 个四分音符)
  - X·   — 附点 (延长 50%)
  - 0    — 休止符
"""
import numpy as np

# 标准化音符时值比例 (相对四分音符=1.0)
# 每个元组: (ratio, name, notation_char)
# 比例 = 音符时值 / 四分音符时值
# 例: 八分音符 = 0.5个四分音符, 二分音符 = 2个四分音符
STANDARD_RATIOS = [
    (0.25, '十六分', 'X\u0332\u0332'),                  # X̲̲
    (0.5,  '八分',   'X\u0332'),                        # X̲
    (0.75, '附点八分', 'X\u0332\u00B7'),                # X̲·
    (1.0,  '四分',   'X'),                              # X
    (1.5,  '附点四分', 'X\u00B7'),                      # X·
    (2.0,  '二分',   'X-'),                              # X-
    (3.0,  '附点二分', 'X-.'),                           # X-.
    (4.0,  '全音符', 'X---'),                            # X---
]

# 用于量化的目标比例
QUANTIZE_RATIOS = [r[0] for r in STANDARD_RATIOS]


def quantize_interval(ioi, bpm, snap_strength=0.8):
    """量化单个击键间隔到标准音符时值

    Args:
        ioi: float — 击键间隔（秒）
        bpm: float — 当前 BPM
        snap_strength: float — 量化力度 [0~1]
            0 = 不量化，保持原始比例
            1 = 完全吸附到最近的标准化比例

    Returns:
        tuple[float, float, str]:
            - quantized_ratio: 量化后的比例 (相对四分音符)
            - closest_ratio: 最接近的标准比例
            - notation_symbol: 简谱符号
    """
    if ioi <= 0 or bpm <= 0:
        return 1.0, 1.0, 'X'

    quarter_dur = 60.0 / bpm
    ratio = ioi / quarter_dur  # 实际比例

    # 寻找最接近的标准比例
    distances = [abs(r - ratio) for r in QUANTIZE_RATIOS]
    closest_idx = int(np.argmin(distances))
    closest_ratio = QUANTIZE_RATIOS[closest_idx]

    # 根据 snap_strength 插值
    snapped_ratio = ratio + (closest_ratio - ratio) * snap_strength

    # 获取对应的简谱符号
    _, _, symbol = STANDARD_RATIOS[closest_idx]

    return snapped_ratio, closest_ratio, symbol


def notation_for_duration(closest_ratio, use_rest=False):
    """根据标准比例返回简谱符号

    Args:
        closest_ratio: float — 标准比例
        use_rest: bool — 是否使用休止符 (0)

    Returns:
        str: 简谱符号
    """
    for ratio, _, symbol in STANDARD_RATIOS:
        if abs(ratio - closest_ratio) < 0.01:
            if use_rest:
                # 休止符：将 X 替换为 0，保留时值标记
                rest_symbol = '0'
                # 保留音符标记后的修饰符（下划线、上划线、附点等）
                base_symbol = symbol
                if base_symbol.startswith('X'):
                    modifiers = base_symbol[1:]
                    rest_symbol = '0' + modifiers
                return rest_symbol
            return symbol
    return '0' if use_rest else 'X'


def format_notation(quantized_notes, bpm, time_sig=(4, 4)):
    """将量化后的音符格式化为简谱字符串

    Args:
        quantized_notes: list[(closest_ratio, symbol_or_str)]
            每个元素是 (标准比例, 简谱符号)
        bpm: float — BPM
        time_sig: tuple[int, int] — 节拍，如 (4,4)

    Returns:
        str: 格式化的简谱字符串，含小节分隔
    """
    if not quantized_notes:
        return '（无音符）'

    beats_per_measure, beat_unit = time_sig

    # 构建完整简谱行
    measures = []
    current_measure_notes = []
    current_dur = 0.0

    for ratio, symbol in quantized_notes:
        current_measure_notes.append(symbol)
        current_dur += ratio

        # 检查是否达到或超过一个小节
        if current_dur >= beats_per_measure - 0.05:
            measures.append(' '.join(current_measure_notes))
            current_measure_notes = []
            current_dur = 0.0

    # 处理最后一小节（可能不完整）
    if current_measure_notes:
        measures.append(' '.join(current_measure_notes))

    # 节拍标记
    header = f"拍号: {time_sig[0]}/{time_sig[1]}  |  BPM: {bpm:.0f}\n"

    # 小节线分隔
    notation = ' | '.join(measures)

    # 添加终止符
    notation += ' ||'

    return header + notation


def format_notation_simple(quantized_notes):
    """简单格式化简谱（无节拍标记，纯音符序列）

    Args:
        quantized_notes: list[(closest_ratio, symbol_or_str)]

    Returns:
        str: 空格分隔的简谱符号
    """
    if not quantized_notes:
        return ''

    symbols = [note[1] for note in quantized_notes]
    return ' '.join(symbols)
