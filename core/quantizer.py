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


def quantize_events(timestamps, bpm, snap_strength=0.8):
    """基于累积位置量化事件序列，保证总拍数正确

    核心思路：
      逐个事件累积拍位置，将每个新位置独立量化到标准音符时值网格上，
      确保量化后的位置差（即音符时值）之和始终等于总拍数。
      这样 measure 分组时就不会出现漏拍或超拍。

    Args:
        timestamps: list[float] — 事件时间戳列表（秒），第一个为起点
        bpm: float — 检测到的 BPM
        snap_strength: float — 量化力度 [0~1]

    Returns:
        list[(closest_ratio, symbol)] — 量化后的 (标准比例, 简谱符号)
    """
    if len(timestamps) < 2:
        return []

    quarter_dur = 60.0 / bpm

    # --- 将时间戳转换为累积拍位置 ---
    start = timestamps[0]
    raw_beats = [(t - start) / quarter_dur for t in timestamps]

    # 如果 snap_strength == 0，完全不量化，直接返回原始间隔
    if snap_strength < 0.01:
        notes = []
        for i in range(1, len(raw_beats)):
            interval = raw_beats[i] - raw_beats[i - 1]
            distances = [abs(r - interval) for r in QUANTIZE_RATIOS]
            idx = int(np.argmin(distances))
            ratio = QUANTIZE_RATIOS[idx]
            _, _, sym = STANDARD_RATIOS[idx]
            notes.append((ratio, sym))
        return notes

    # --- 基于累积位置量化 ---
    q_positions = [0.0]  # 第一个音符位置 = 0
    q_notes = []

    for i in range(1, len(raw_beats)):
        raw_interval = raw_beats[i] - q_positions[-1]
        if raw_interval <= 0:
            raw_interval = 0.25  # 极小间隔兜底

        # 找到最近的标准比例
        distances = [abs(r - raw_interval) for r in QUANTIZE_RATIOS]
        closest_idx = int(np.argmin(distances))
        closest_ratio = QUANTIZE_RATIOS[closest_idx]

        # 按 snap_strength 插值得到量化后的间隔
        snapped = raw_interval + (closest_ratio - raw_interval) * snap_strength
        snapped = max(snapped, 0.125)  # 最小 1/32 音符

        # 新的累积拍位置
        new_q_pos = q_positions[-1] + snapped
        q_positions.append(new_q_pos)

        # 确定实际输出使用的标准比例（从 snapped 重映射到标准值）
        d2 = [abs(r - snapped) for r in QUANTIZE_RATIOS]
        out_idx = int(np.argmin(d2))
        out_ratio = QUANTIZE_RATIOS[out_idx]
        _, _, symbol = STANDARD_RATIOS[out_idx]
        q_notes.append((out_ratio, symbol))

    return q_notes


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
    tolerance = 0.05  # 浮点数容差
    min_note = min(QUANTIZE_RATIOS)  # 最小音符时值（0.25拍）

    # 构建完整简谱行
    measures = []
    current_measure_notes = []  # (ratio, symbol)
    current_dur = 0.0

    def _close_measure():
        """封小节：补足不够的拍数（插入休止符），然后加入 measures"""
        nonlocal current_dur, current_measure_notes
        if current_dur < beats_per_measure - tolerance:
            shortfall = beats_per_measure - current_dur
            # 找到最接近的休止符时值来补足
            if shortfall >= min_note - tolerance:
                best_ratio = None
                best_dist = float('inf')
                for r in QUANTIZE_RATIOS:
                    if r <= shortfall + tolerance:
                        dist = abs(r - shortfall)
                        if dist < best_dist:
                            best_dist = dist
                            best_ratio = r
                if best_ratio is not None and best_ratio >= min_note:
                    rest_symbol = notation_for_duration(best_ratio, use_rest=True)
                    current_measure_notes.append((best_ratio, rest_symbol))
                    current_dur += best_ratio

        if current_measure_notes:
            symbols = [s for _, s in current_measure_notes]
            measures.append(' '.join(symbols))
        current_measure_notes = []
        current_dur = 0.0

    for ratio, symbol in quantized_notes:
        # 如果当前小节已有音符，且加入此音符后会显著超出一小节 -> 先封小节
        if (current_dur > tolerance
                and current_dur + ratio > beats_per_measure + tolerance):
            _close_measure()

        current_measure_notes.append((ratio, symbol))
        current_dur += ratio

        # 恰好或几乎填满一小节 -> 立即封小节
        if abs(current_dur - beats_per_measure) < tolerance:
            _close_measure()

    # 处理最后一小节（不补休止符，保留原样）
    if current_measure_notes:
        symbols = [s for _, s in current_measure_notes]
        measures.append(' '.join(symbols))

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
