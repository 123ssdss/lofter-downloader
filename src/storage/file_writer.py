"""
src/storage/file_writer.py
统一文件写入层 — 所有磁盘 I/O 操作集中在此，其他模块不直接写文件。
"""
import json
import os
from typing import Any, Dict


class FileWriter:
    """提供 JSON / 文本 两种写入方式，自动创建缺失的目录。"""

    @staticmethod
    def write_json(data: Any, filepath: str) -> str:
        """
        将任意可 JSON 序列化的对象保存为 UTF-8 编码的 .json 文件。
        返回写入路径；失败时返回空字符串。
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            print(f"[FileWriter] 写入 JSON 失败 {filepath}: {e}")
            return ""

    @staticmethod
    def write_text(content: str, filepath: str) -> str:
        """
        将字符串保存为 UTF-8 编码的文本文件。
        返回写入路径；失败时返回空字符串。
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return filepath
        except Exception as e:
            print(f"[FileWriter] 写入文本失败 {filepath}: {e}")
            return ""

    @staticmethod
    def read_json(filepath: str) -> Any:
        """读取 JSON 文件，失败时返回 None。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
