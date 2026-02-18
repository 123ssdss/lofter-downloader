"""
src/progress.py
轻量级进度条工具，在终端实时刷新一行显示进度
"""
import sys
import time
from typing import Optional


def _format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def _draw_bar(progress: float, width: int = 30) -> str:
    filled = int(progress * width)
    bar_chars = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    bar = ""
    for i in range(width):
        if i < filled:
            bar += "█"
        elif i == filled:
            partial = min(int((progress * width - filled) * 8), 7)
            bar += bar_chars[partial + 1]
        else:
            bar += "░"
    return bar


class ProgressBar:
    """
    单行刷新式进度条。
    用法：
        pb = ProgressBar(total=100, label="处理帖子")
        pb.start()
        for i in range(100):
            pb.update(i + 1)
        pb.finish()
    """

    def __init__(self, total: int, label: str = "", width: int = 30):
        self.total      = max(total, 1)
        self.label      = label
        self.width      = width
        self._start_ts: Optional[float] = None

    def start(self) -> None:
        self._start_ts = time.time()
        self._render(0)

    def update(self, current: int) -> None:
        self._render(current)

    def finish(self) -> None:
        self._render(self.total)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def _render(self, current: int) -> None:
        if self._start_ts is None:
            self._start_ts = time.time()

        elapsed  = time.time() - self._start_ts
        progress = current / self.total
        bar      = _draw_bar(progress, self.width)
        pct      = progress * 100

        # ETA
        if current > 0 and progress < 1.0:
            eta_sec = elapsed / progress * (1 - progress)
            eta_str = f"ETA {_format_time(eta_sec)}"
        else:
            eta_str = _format_time(elapsed)

        label_str = f"{self.label} " if self.label else ""
        line = (
            f"\r{label_str}[{bar}] {current}/{self.total} "
            f"({pct:.1f}%) {eta_str}   "
        )
        sys.stdout.write(line)
        sys.stdout.flush()
