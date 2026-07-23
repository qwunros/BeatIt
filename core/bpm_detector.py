"""
BPM 检测模块

自动检测策略：
  1. 计算击键间隔 (IOI) 直方图，找到峰值间隔 base_interval
  2. 按 k ∈ {1,2,3,4,6,8} 生成候选 BPM = 60 / (base_interval/k)
  3. 筛选 [40, 280] 范围，取最大值

手动调节：
  以 2 的整数幂次倍率调节 BPM（×½, ×1, ×2, ×4, ×8）
"""
import numpy as np

# BPM 有效范围
BPM_MIN = 40
BPM_MAX = 280

# 音符细分层级 (对应不同节拍感知级别)
SUBDIVISIONS = [1, 2, 3, 4, 6, 8]


def detect_bpm(intervals):
    """从击键间隔列表中自动检测 BPM

    Args:
        intervals: list[float] — 相邻击键的时间间隔（秒）

    Returns:
        tuple[float, float]: (检测到的 BPM, 置信度 0~1)
    """
    if len(intervals) < 2:
        return 120.0, 0.0  # 数据不足，返回默认值

    # 过滤异常值（超过 5 秒的间隔视为停顿）
    filtered = [i for i in intervals if 0.05 < i < 5.0]
    if len(filtered) < 2:
        return 120.0, 0.0

    # --- 构建直方图找峰值 ---
    max_interval = min(max(filtered), 3.0)  # 上限 3 秒
    bin_width = 0.02  # 20ms 精度
    bins = np.arange(0, max_interval + bin_width, bin_width)
    hist, edges = np.histogram(filtered, bins=bins)

    if np.max(hist) == 0:
        return 120.0, 0.0

    # 找到最高峰值所在的 bin
    peak_idx = np.argmax(hist)
    base_interval = (edges[peak_idx] + edges[peak_idx + 1]) / 2.0

    if base_interval <= 0:
        return 120.0, 0.0

    # --- 生成候选 BPM ---
    candidates = []
    for k in SUBDIVISIONS:
        bpm = 60.0 / (base_interval / k)
        candidates.append(bpm)

    # --- 从 [40, 280] 中取最大 ---
    valid = [b for b in candidates if BPM_MIN <= b <= BPM_MAX]

    if valid:
        bpm = max(valid)
    elif all(b < BPM_MIN for b in candidates):
        bpm = float(BPM_MIN)
    else:
        bpm = float(BPM_MAX)

    # 置信度: 基于峰值高度占比
    total_intervals = len(filtered)
    confidence = min(hist[peak_idx] / max(total_intervals * 0.3, 1), 1.0)

    return round(bpm, 1), round(confidence, 2)


def detect_bpm_sliding(intervals, window_size=20):
    """滑动窗口 BPM 检测（用于实时模式）

    只取最近 window_size 个间隔进行检测，适应节奏变化。

    Args:
        intervals: list[float] — 全部击键间隔
        window_size: int — 滑动窗口大小

    Returns:
        tuple[float, float]: (BPM, 置信度)
    """
    if len(intervals) < 4:
        return 120.0, 0.0

    recent = intervals[-window_size:]
    return detect_bpm(recent)


def manual_adjust(bpm, multiplier):
    """手动以 2 的幂次倍率调节 BPM

    Args:
        bpm: float — 当前 BPM
        multiplier: float — 必须是 2 的整数幂 (0.5, 1, 2, 4, 8...)

    Returns:
        float: 调整后的 BPM
    """
    new_bpm = bpm * multiplier
    # 允许手动调节超出 [40, 280] 范围
    return round(max(1.0, new_bpm), 1)
