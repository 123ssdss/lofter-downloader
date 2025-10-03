import time
import os
import shutil
import sys


def format_time(seconds):
    """Formats seconds into a human-readable string (s, m, h)."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def draw_progress_bar(progress, width=40):
    """Draws a Unicode-based progress bar."""
    filled = int(progress * width)
    bar_chars = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    bar = ""
    for i in range(width):
        if i < filled:
            bar += "█"
        elif i == filled:
            partial_idx = min(int((progress * width - filled) * 8), 7)
            bar += bar_chars[partial_idx + 1]
        else:
            bar += "░"
    return bar


def display_progress(current, total, start_time, tag=None):
    """Displays a progress summary in the console."""
    if total == 0:
        return
    progress = current / total
    elapsed = time.time() - start_time
    avg_time = elapsed / current if current > 0 else 0
    remaining = (total - current) * avg_time if current > 0 else 0

    progress_bar = draw_progress_bar(progress)
    
    # Spinner for active state
    spinner_frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    spinner = spinner_frames[int(time.time() * 10) % len(spinner_frames)] if progress < 1.0 else "✅"

    # Using simple ASCII characters instead of Unicode to avoid encoding issues on Windows
    info = (
        f"Progress: {current}/{total} ({progress:.1%}) | Tag: {tag or 'N/A'}\n"
        f"Time: Elapsed: {format_time(elapsed)} | Remaining: {format_time(remaining)} | Avg: {avg_time:.2f}s/post\n"
        f"[{spinner}] [{progress_bar}] {progress:.1%}"
    )
    
    # Move cursor up and clear lines to overwrite previous progress
    # Use sys.stdout.write to avoid encoding issues
    try:
        sys.stdout.write("\033[F\033[K" * 3)
        sys.stdout.write(info + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Fallback for systems that can't display Unicode characters
        fallback_info = f"Progress: {current}/{total} ({progress:.1%}) | Tag: {tag or 'N/A'} | Time: {format_time(elapsed)}"
        sys.stdout.write(fallback_info + "\n")
        sys.stdout.flush()


def clear_directory(directory):
    """Removes all files and subdirectories in a given directory."""
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)


# 导入 path_manager 模块中的 path_manager 实例
from .path_manager import path_manager

# 定义包的公共接口
__all__ = [
    'display_progress',
    'format_time', 
    'draw_progress_bar',
    'clear_directory',
    'path_manager'
]