"""连续帧会话化：把逐帧 mounting 检出聚合为"行为窗口"，一个窗口 = 一个事件。

解决同一行为连续几十帧产生几十个重复告警的问题：
- 连续 >= k_open 帧置信度超过 conf_thresh 才开窗（过滤单帧抖动误检）；
- 开窗后连续 >= m_close 帧低于阈值才关窗（容忍短暂遮挡/漏检）；
- 关窗时被 m_close 吞掉的尾部低分帧不计入窗口。
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FrameDetection:
    """单帧 mounting 检出摘要：该帧最高 mounting 置信度（无检出为 0.0）。"""

    frame_index: int
    confidence: float
    bbox: Optional[List[float]] = None


@dataclass
class BehaviorWindow:
    """一个行为窗口 = 一次爬跨事件。"""

    start_frame: int
    end_frame: int
    peak_confidence: float
    peak_frame: int
    best_bbox: Optional[List[float]]
    avg_confidence: float


def _build_window(frames: List[FrameDetection]) -> BehaviorWindow:
    peak = max(frames, key=lambda f: f.confidence)
    avg = round(sum(f.confidence for f in frames) / len(frames), 4)
    return BehaviorWindow(
        start_frame=frames[0].frame_index,
        end_frame=frames[-1].frame_index,
        peak_confidence=peak.confidence,
        peak_frame=peak.frame_index,
        best_bbox=peak.bbox,
        avg_confidence=avg,
    )


def sessionize(
    frames: List[FrameDetection],
    conf_thresh: float = 0.4,
    k_open: int = 3,
    m_close: int = 5,
) -> List[BehaviorWindow]:
    windows: List[BehaviorWindow] = []
    pending: List[FrameDetection] = []  # 开窗候选：连续高帧但未达 k_open
    win: List[FrameDetection] = []      # 当前窗口跨度内的全部帧（含短暂低分帧）
    below = 0                           # 窗口内连续低于阈值的帧数
    in_window = False

    for f in frames:
        if not in_window:
            if f.confidence >= conf_thresh:
                pending.append(f)
                if len(pending) >= k_open:
                    in_window = True
                    win = pending
                    pending = []
                    below = 0
            else:
                pending = []
            continue

        win.append(f)
        if f.confidence >= conf_thresh:
            below = 0
        else:
            below += 1
            if below >= m_close:
                windows.append(_build_window(win[:-m_close]))
                in_window = False
                win = []
                below = 0

    if in_window:
        # 流结束仍未关窗：强制关窗，尾部低于阈值的帧不计入
        tail = win[:-below] if below else win
        windows.append(_build_window(tail))
    return windows
