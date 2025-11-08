"""
美化日志工具
提供更美观、易读的日志输出
"""
import logging
import sys
import os
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def __init__(self, format_type='default'):
        self.format_type = format_type
        super().__init__()
    
    def format(self, record):
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # 根据格式类型调整显示
        if self.format_type == 'simple':
            # 简单格式
            levelname = record.levelname
            if record.levelname == 'WARNING':
                levelname = 'WARN'
            elif record.levelname == 'CRITICAL':
                levelname = 'CRIT'
            
            message = f"{color}[{levelname}]{reset} {record.getMessage()}"
            return message
        
        elif self.format_type == 'detailed':
            # 详细格式
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            levelname = record.levelname.ljust(8)
            name = record.name[:15].ljust(15)
            
            message = f"{color}[{timestamp}]{reset} {color}[{levelname}]{reset} {name} {record.getMessage()}"
            return message
        
        else:  # default
            # 默认格式
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            levelname = record.levelname.ljust(8)
            
            message = f"{color}[{timestamp}]{reset} {color}[{levelname}]{reset} {record.getMessage()}"
            return message


class BeautifulLogger:
    """美化日志器"""
    
    @staticmethod
    def setup_logger(name: str = None, level: int = logging.INFO, 
                    format_type: str = 'default', enable_color: bool = True) -> logging.Logger:
        """
        设置美化日志器
        
        Args:
            name: 日志器名称
            level: 日志级别
            format_type: 格式类型 ('simple', 'detailed', 'default')
            enable_color: 是否启用颜色
        """
        logger = logging.getLogger(name or 'LofterCrawler')
        
        # 清除已有处理器
        logger.handlers.clear()
        
        # 创建处理器
        handler = logging.StreamHandler()
        
        # Windows控制台颜色支持检测
        if enable_color and sys.platform == 'win32':
            # Windows 10+ 支持颜色
            import colorama
            try:
                colorama.init()
            except:
                enable_color = False
        
        # 设置格式化器
        if enable_color:
            formatter = ColoredFormatter(format_type)
        else:
            # 不用颜色的格式化器
            if format_type == 'simple':
                formatter = logging.Formatter('[%(levelname)s] %(message)s')
            elif format_type == 'detailed':
                formatter = logging.Formatter('[%(asctime)s] [%(levelname)-8s] [%(name)-15s] %(message)s')
            else:
                formatter = logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(message)s')
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        
        return logger
    
    @staticmethod
    def create_progress_logger(name: str = "Progress") -> logging.Logger:
        """创建进度日志器"""
        return BeautifulLogger.setup_logger(name, level=logging.INFO, format_type='simple', enable_color=True)
    
    @staticmethod
    def create_debug_logger(name: str = "Debug") -> logging.Logger:
        """创建调试日志器"""
        return BeautifulLogger.setup_logger(name, level=logging.DEBUG, format_type='detailed', enable_color=True)


class ProgressDisplay:
    """进度显示工具"""
    
    def __init__(self, total: int, description: str = "Processing", unit: str = "items", update_frequency: int = 5):
        self.total = total
        self.current = 0
        self.description = description
        self.unit = unit
        self.start_time = datetime.now()
        self.logger = BeautifulLogger.create_progress_logger()
        self.update_frequency = max(1, update_frequency)  # 至少每1个更新一次
        self.last_update = 0
        self.last_progress_line = ""  # 记录上次进度条内容，用于刷新
        self.progress_active = False  # 标记进度条是否激活
    
    def _clear_progress_line(self):
        """清除当前进度条行"""
        try:
            # 获取终端大小
            import shutil
            cols, rows = shutil.get_terminal_size((80, 24))
            # 移动到终端底部并清除整行
            sys.stdout.write(f"\033[{rows};1H")
            sys.stdout.write(f"\033[K")
            sys.stdout.flush()
        except:
            pass
    
    def _restore_progress_line(self, progress_line):
        """恢复进度条到最后一行"""
        try:
            # 获取终端大小
            import shutil
            cols, rows = shutil.get_terminal_size((80, 24))
            # 移动到终端底部并显示进度条
            sys.stdout.write(f"\033[{rows};1H")
            sys.stdout.write(f"\033[K")
            sys.stdout.write(progress_line)
            sys.stdout.flush()
        except:
            pass
    
    def update(self, current: int = None, description: str = None):
        """更新进度"""
        if current is not None:
            self.current = current
        if description is not None:
            self.description = description
            
        # 只在达到更新频率时才显示进度
        if self.current - self.last_update < self.update_frequency and self.current < self.total:
            if self.current >= self.total:
                # 完成时总是显示
                pass
            else:
                return
        
        percentage = (self.current / self.total) * 100 if self.total > 0 else 100
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f"ETA: {eta:.1f}s" if eta > 0 else "Complete"
        else:
            eta_str = "ETA: --"
        
        # 创建进度条
        bar_length = 30
        filled_length = int(bar_length * self.current // self.total)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # 构造进度条信息
        progress_info = f"{self.description}: |{bar}| {self.current}/{self.total} ({percentage:.1f}%) {eta_str}"
        # 添加前缀符号以匹配项目中的显示格式
        prefix = "⟂ " if self.current < self.total else "✓ "
        message = f"{prefix}{progress_info}"
        
        # 保存当前进度条内容
        self.last_progress_line = message
        self.progress_active = True
        
        # 清除当前行并显示新的进度条
        self._clear_progress_line()
        self._restore_progress_line(message)
        
        # 记录最后更新时间
        if self.current < self.total:
            self.last_update = self.current
        
        if self.current >= self.total:
            # 完成时换行并显示完成信息
            self._clear_progress_line()
            self.progress_active = False
            self.logger.info(f"[COMPLETE] {self.description} completed! Processed {self.total} {self.unit}.")


class StatusDisplay:
    """状态显示工具"""
    
    @staticmethod
    def print_header(title: str, info: dict = None, width: int = 80):
        """打印标题"""
        print("\n" + "=" * width)
        print(f"  {title.center(width - 4)}  ")
        if info:
            print("-" * width)
            # 格式化信息
            for key, value in info.items():
                if value is not None and value != "":
                    print(f"  {key}: {value}")
            print("-" * width)
        print("=" * width)
    
    @staticmethod
    def print_section(title: str, width: int = 50):
        """打印章节标题"""
        print(f"\n[TITLE] {title}")
        print("-" * (len(title) + 9))
    
    @staticmethod
    def print_success(message: str):
        """打印成功信息"""
        print(f"[SUCCESS] {message}")
    
    @staticmethod
    def print_error(message: str):
        """打印错误信息"""
        print(f"[ERROR] {message}")
    
    @staticmethod
    def print_warning(message: str):
        """打印警告信息"""
        print(f"[WARNING] {message}")
    
    @staticmethod
    def print_info(message: str):
        """打印信息"""
        print(f"[INFO] {message}")



def format_duration(seconds: float) -> str:
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
