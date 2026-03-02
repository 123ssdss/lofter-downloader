"""
src/logger.py
统一日志模块，提供彩色终端输出和静态状态打印工具
"""
import logging
import sys
from typing import Optional


# ANSI 颜色代码
class _C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"
    BLUE   = "\033[34m"
    MAGENTA= "\033[35m"


class _ColoredFormatter(logging.Formatter):
    """为不同日志级别添加 ANSI 颜色"""

    _LEVEL_COLORS = {
        logging.DEBUG:    _C.WHITE,
        logging.INFO:     _C.GREEN,
        logging.WARNING:  _C.YELLOW,
        logging.ERROR:    _C.RED,
        logging.CRITICAL: _C.BOLD + _C.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self._LEVEL_COLORS.get(record.levelno, _C.RESET)
        level_tag = f"{color}[{record.levelname[:4]}]{_C.RESET}"
        name_tag  = f"{_C.CYAN}[{record.name}]{_C.RESET}"
        message   = super().format(record)
        # 去掉原始格式中的 levelname 前缀，只保留消息
        msg_only  = record.getMessage()
        return f"{level_tag} {name_tag} {msg_only}"


def get_logger(name: str, debug: bool = False) -> logging.Logger:
    """
    获取一个带颜色格式的 logger。
    同一 name 多次调用会返回同一实例（Python logging 的行为）。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # 已经初始化过，直接返回
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        return logger

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColoredFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# ── 静态状态打印工具（用于 main.py 的横幅、摘要输出）──────────────

class StatusDisplay:
    """简单的静态终端打印工具（不走 logging 系统）"""

    @staticmethod
    def print_header(title: str, info: Optional[dict] = None) -> None:
        print(f"\n{_C.BOLD}{_C.CYAN}{'=' * 60}{_C.RESET}")
        print(f"{_C.BOLD}{_C.CYAN}  {title}{_C.RESET}")
        if info:
            for k, v in info.items():
                print(f"  {_C.WHITE}{k}:{_C.RESET} {v}")
        print(f"{_C.BOLD}{_C.CYAN}{'=' * 60}{_C.RESET}\n")

    @staticmethod
    def print_section(title: str) -> None:
        print(f"\n{_C.BOLD}{_C.BLUE}── {title} {'─' * max(0, 50 - len(title))}{_C.RESET}")

    @staticmethod
    def print_info(msg: str) -> None:
        print(f"{_C.GREEN}[INFO]{_C.RESET}  {msg}")

    @staticmethod
    def print_success(msg: str) -> None:
        print(f"{_C.GREEN}[OK]  {_C.RESET}  {msg}")

    @staticmethod
    def print_warning(msg: str) -> None:
        print(f"{_C.YELLOW}[WARN]{_C.RESET}  {msg}")

    @staticmethod
    def print_error(msg: str) -> None:
        print(f"{_C.RED}[ERR] {_C.RESET}  {msg}")
