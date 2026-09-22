from app.services.behavior_session import FrameDetection, sessionize


def make_frames(confs):
    return [
        FrameDetection(
            frame_index=i,
            confidence=c,
            bbox=[float(i), 0.0, 1.0, 1.0] if c > 0 else None,
        )
        for i, c in enumerate(confs)
    ]


def test_single_window_open_close():
    frames = make_frames([0.0, 0.0, 0.5, 0.6, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0])
    windows = sessionize(frames)
    assert len(windows) == 1
    w = windows[0]
    assert w.start_frame == 2
    assert w.end_frame == 4
    assert w.peak_confidence == 0.7
    assert w.peak_frame == 4


def test_two_windows_separated():
    frames = make_frames(
        [0.5, 0.5, 0.5] + [0.0] * 5 + [0.6, 0.6, 0.6] + [0.0] * 5)
    windows = sessionize(frames)
    assert len(windows) == 2
    assert (windows[0].start_frame, windows[0].end_frame) == (0, 2)
    assert (windows[1].start_frame, windows[1].end_frame) == (8, 10)


def test_k_open_not_reached_no_window():
    # 只有 2 帧超阈值，达不到 k_open=3，不开窗
    frames = make_frames([0.9, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert sessionize(frames) == []


def test_m_close_not_reached_keeps_window():
    # 窗口内 4 帧低于阈值（< m_close=5）不关窗，之后恢复高分仍属同一窗口
    frames = make_frames(
        [0.5, 0.5, 0.5] + [0.0] * 4 + [0.6] + [0.0] * 5)
    windows = sessionize(frames)
    assert len(windows) == 1
    assert windows[0].start_frame == 0
    assert windows[0].end_frame == 7


def test_window_aggregation_values():
    frames = make_frames([0.5, 0.6, 0.9, 0.5] + [0.0] * 5)
    windows = sessionize(frames)
    assert len(windows) == 1
    w = windows[0]
    assert w.peak_confidence == 0.9
    assert w.peak_frame == 2
    assert w.best_bbox == [2.0, 0.0, 1.0, 1.0]
    assert w.avg_confidence == round((0.5 + 0.6 + 0.9 + 0.5) / 4, 4)


def test_empty_input():
    assert sessionize([]) == []


def test_open_window_force_closed_at_stream_end():
    # 流结束时窗口未关：强制关窗，尾部低分帧不计入
    frames = make_frames([0.5, 0.6, 0.7, 0.0, 0.0])
    windows = sessionize(frames)
    assert len(windows) == 1
    w = windows[0]
    assert w.start_frame == 0
    assert w.end_frame == 2
    assert w.peak_confidence == 0.7
