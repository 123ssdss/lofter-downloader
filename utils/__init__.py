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

def get_terminal_size():
    """Get terminal size (columns, rows)"""
    try:
        return shutil.get_terminal_size()
    except:
        return (80, 24)  # Default fallback
class TerminalProgress:
    """高级终端进度展示模块"""
    
    def __init__(self):
        self.progress_active = False
        self.start_time = None
        self.last_progress_line = ""  # 记录上一次的进度条内容
        
    def _clear_progress_line(self):
        """清除当前进度条行"""
        if self.progress_active:
            try:
                cols, rows = get_terminal_size()
                # 移动到终端底部并清除整行
                sys.stdout.write(f"\033[{rows};1H")
                sys.stdout.write(f"\033[K")
                sys.stdout.flush()
            except:
                pass
    
    def _restore_progress_line(self):
        """恢复进度条到最后一行"""
        if self.progress_active and self.last_progress_line:
            try:
                cols, rows = get_terminal_size()
                # 移动到终端底部并显示进度条
                sys.stdout.write(f"\033[{rows};1H")
                sys.stdout.write(f"\033[K")
                sys.stdout.write(self.last_progress_line)
                sys.stdout.flush()
            except:
                pass
    
    def log_info(self, message):
        """上方正常输出info信息，不覆盖历史内容"""
        # 如果有活动的进度条，需要先清除它
        if self.progress_active:
            self._clear_progress_line()
        print(f"[INFO] {message}")
        sys.stdout.flush()
        # 如果有活动的进度条，需要恢复它
        if self.progress_active:
            self._restore_progress_line()
    
    def display_progress(self, current, total, tag=None, description="Processing"):
        """进度条常驻终端底部，实时刷新进度值"""
        if total == 0:
            return
        
        # 初始化进度
        if not self.progress_active:
            self.start_time = time.time()
            self.progress_active = True
            
            # 显示初始进度
            self._update_progress_bar(current, total, tag, description, initial=True)
            return
        
        # 更新现有进度条
        self._update_progress_bar(current, total, tag, description, initial=False)
    
    def _update_progress_bar(self, current, total, tag, description, initial=False):
        """更新进度条显示"""
        progress = current / total
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # 创建进度条
        bar_width = 35
        filled_width = int(progress * bar_width)
        bar = '█' * filled_width + '░' * (bar_width - filled_width)
        
        # 状态信息
        status = "✅" if progress >= 1.0 else ""
        percentage = f"{progress:.1%}"
        
        # 进度信息
        progress_text = f"{description}: [{bar}] {current}/{total} ({percentage})"
        if tag:
            progress_text += f" | {tag}"
        
        # 添加时间信息
        if elapsed > 0:
            time_info = f"⏱ {format_time(elapsed)}"
            progress_text += f" {time_info}"
        
        # 保存进度条内容
        self.last_progress_line = progress_text
        
        try:
            # 移动到终端底部并显示进度条
            cols, rows = get_terminal_size()
            sys.stdout.write(f"\033[{rows};1H")  # 移动到最底部
            sys.stdout.write(f"\033[K")  # 清除整行
            sys.stdout.write(f"\033[1m{progress_text}\033[0m")  # 白色粗体
            sys.stdout.flush()
                
        except (UnicodeEncodeError, OSError):
            # 兼容方案 - 确保不与INFO信息在同一行
            pass  # 不输出进度条，避免与INFO信息在同一行
    
    def finish_progress(self, message="Completed"):
        """完成进度条并恢复终端"""
        if self.progress_active:
            # 清除进度条
            try:
                cols, rows = get_terminal_size()
                sys.stdout.write(f"\033[{rows};1H")
                sys.stdout.write(f"\033[K")
                sys.stdout.flush()
            except:
                pass
            
            self.progress_active = False
            self.last_progress_line = ""
            
            # 显示完成信息
            print(f"[SUCCESS] {message}")

def display_progress(current, total, start_time, tag=None, description="Processing"):
    """简化的进度条函数，兼容现有代码"""
    if not hasattr(display_progress, 'terminal'):
        display_progress.terminal = TerminalProgress()
        display_progress.terminal.start_time = start_time
    
    # 如果是新的任务，重置状态
    if start_time != display_progress.terminal.start_time:
        display_progress.terminal.progress_active = False
        display_progress.terminal.start_time = start_time
    
    # 显示进度
    display_progress.terminal.display_progress(current, total, tag, description)
    
    # 如果完成，清理状态
    if current >= total:
        display_progress.terminal.finish_progress("所有任务完成")

# 保持向后兼容
def safe_print(message):
    """安全打印函数，向后兼容"""
    print(message)
    sys.stdout.flush()

def format_time(seconds):
    """Format time duration in a human readable way"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

# 导入 path_manager 模块中的 path_manager 实例
from .path_manager import path_manager

# 导入新的终端进度管理器
from .terminal_progress import (
    TerminalProgressManager,
    log_info,
    log_warning,
    log_error,
    start_progress,
    update_progress,
    finish_progress
)

# 定义包的公共接口
__all__ = [
    'display_progress',
    'safe_print',
    'TerminalProgress',
    'format_time', 
    'draw_progress_bar',
    'clear_directory',
    'path_manager',
    'TerminalProgressManager',
    'log_info',
    'log_warning',
    'log_error',
    'start_progress',
    'update_progress',
    'finish_progress'
]