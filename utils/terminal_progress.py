# -*- coding: utf-8 -*-
"""
终端进度展示模块
实现功能：
1. 上方持续输出info信息，不覆盖历史内容
2. 进度条常驻终端底部，实时刷新进度值
3. 避免进度条与日志内容错乱、换行重叠
"""

import sys
import time
import shutil
import threading
from typing import Optional


class TerminalProgressManager:
    """终端进度管理器"""
    
    def __init__(self):
        self.progress_active = False
        self.start_time = None
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        self.current = 0
        self.total = 0
        self.description = ""
        self.tag = ""
        self.last_terminal_size = (80, 24)
        self.last_progress_line = ""  # 记录上次进度条内容，用于刷新
        
    def get_terminal_size(self):
        """获取终端大小"""
        try:
            return shutil.get_terminal_size()
        except:
            return self.last_terminal_size
    
    def _clear_progress_line(self):
        """清除当前进度条行"""
        if self.progress_active:
            cols, rows = self.get_terminal_size()
            sys.stdout.write(f"\033[{rows};1H")  # 移动到最底部行
            sys.stdout.write(f"\033[K")  # 清除整行
    
    def _restore_progress_line(self):
        """恢复进度条到最后一行"""
        if self.progress_active and self.last_progress_line:
            cols, rows = self.get_terminal_size()
            sys.stdout.write(f"\033[{rows};1H")  # 移动到最底部行
            sys.stdout.write(f"\033[K")  # 清除整行
            sys.stdout.write(self.last_progress_line)
            sys.stdout.flush()
    
    def log_info(self, message: str):
        """在上方输出info信息，不覆盖历史内容"""
        with self.lock:
            # 如果有活动的进度条，需要先清除它
            if self.progress_active:
                self._clear_progress_line()
            
            # 输出信息
            print(f"[INFO] {message}")
            sys.stdout.flush()
            
            # 如果有活动的进度条，需要恢复它
            if self.progress_active:
                self._restore_progress_line()
    
    def log_warning(self, message: str):
        """在上方输出warning信息"""
        with self.lock:
            if self.progress_active:
                self._clear_progress_line()
            
            print(f"[WARNING] {message}")
            sys.stdout.flush()
            
            if self.progress_active:
                self._restore_progress_line()
    
    def log_error(self, message: str):
        """在上方输出error信息"""
        with self.lock:
            if self.progress_active:
                self._clear_progress_line()
            
            print(f"[ERROR] {message}")
            sys.stdout.flush()
            
            if self.progress_active:
                self._restore_progress_line()
    
    def start_progress(self, total: int, description: str = "Processing", tag: str = ""):
        """开始进度显示"""
        with self.lock:
            self.current = 0
            self.total = total
            self.description = description
            self.tag = tag
            self.start_time = time.time()
            self.progress_active = True
            
            # 显示初始进度条
            self._update_progress_bar()
    
    def update_progress(self, current: int, description: Optional[str] = None, tag: Optional[str] = None):
        """更新进度"""
        with self.lock:
            if not self.progress_active:
                return
                
            self.current = current
            if description is not None:
                self.description = description
            if tag is not None:
                self.tag = tag
            
            self._update_progress_bar()
    
    def _update_progress_bar(self):
        """更新进度条显示"""
        if not self.progress_active or self.total == 0:
            return
        
        # 计算进度和时间
        progress = min(1.0, self.current / self.total)
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # 创建进度条
        bar_width = 35
        filled_width = int(progress * bar_width)
        bar = '█' * filled_width + '░' * (bar_width - filled_width)
        
        # 状态指示符
        status = "✅" if progress >= 1.0 else ""
        
        # 进度信息
        progress_text = f"{self.description}: [{bar}] {self.current}/{self.total} ({progress:.1%})"
        
        # 添加标签
        if self.tag:
            progress_text += f" | {self.tag}"
        
        # 添加时间信息
        if elapsed > 0:
            time_info = f"⏱ {self._format_time(elapsed)}"
            progress_text += f" {time_info}"
        
        # 获取终端大小
        cols, rows = self.get_terminal_size()
        self.last_terminal_size = (cols, rows)
        
        try:
            # 移动到终端底部并显示进度条
            sys.stdout.write(f"\033[{rows};1H")  # 移动到最底部行
            sys.stdout.write(f"\033[K")  # 清除整行
            sys.stdout.write(f"\033[1m\033[36m{progress_text}\033[0m")  # 蓝色粗体
            sys.stdout.flush()
        except (UnicodeEncodeError, OSError):
            # 兼容方案 - 确保不与INFO信息在同一行
            pass  # 不输出进度条，避免与INFO信息在同一行
        
        # 保存当前进度条内容，用于之后的更新
        self.last_progress_line = progress_text
    
    def finish_progress(self, message: str = "Completed"):
        """完成进度显示"""
        with self.lock:
            if not self.progress_active:
                return
            
            # 清除进度条
            self._clear_progress_line()
            
            self.progress_active = False
            self.start_time = None
            self.last_progress_line = ""
            
            # 显示完成信息
            print(f"[SUCCESS] {message}")
            sys.stdout.flush()
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}h {minutes}m {secs:.1f}s"


# 全局进度管理器实例
_progress_manager = TerminalProgressManager()


def log_info(message: str):
    """全局info日志函数"""
    _progress_manager.log_info(message)


def log_warning(message: str):
    """全局warning日志函数"""
    _progress_manager.log_warning(message)


def log_error(message: str):
    """全局error日志函数"""
    _progress_manager.log_error(message)


def start_progress(total: int, description: str = "Processing", tag: str = ""):
    """开始进度显示"""
    _progress_manager.start_progress(total, description, tag)


def update_progress(current: int, description: Optional[str] = None, tag: Optional[str] = None):
    """更新进度"""
    _progress_manager.update_progress(current, description, tag)


def finish_progress(message: str = "Completed"):
    """完成进度显示"""
    _progress_manager.finish_progress(message)


# 向后兼容函数
def display_progress(current, total, start_time, tag=None, description="Processing"):
    """向后兼容的进度显示函数"""
    if not hasattr(display_progress, 'initialized') or display_progress.last_total != total:
        start_progress(total, description, tag or "")
        display_progress.initialized = True
        display_progress.last_total = total
        display_progress.start_time = start_time
    else:
        # 更新描述和标签
        update_progress(current, description, tag)
        
        # 如果完成，清理状态
        if current >= total:
            elapsed = time.time() - display_progress.start_time if display_progress.start_time else 0
            finish_progress(f"{description} completed in {display_progress._format_time(elapsed)}")


# 为向后兼容函数添加辅助方法
display_progress._format_time = _progress_manager._format_time
display_progress.last_total = 0
display_progress.start_time = None