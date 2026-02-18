"""
src/storage/path_manager.py
路径管理器 — 统一所有输出路径的构造逻辑。
与原版目录结构完全一致：
  output/<mode>/<name>/
  json/<mode>/<name>/<sub>/
  photo/<mode>/<name>/
"""
import os
from typing import Optional

import config

# 合法的 mode 值
_VALID_MODES = {"tag", "blog", "collection", "comment", "subscription", "update"}


class PathManager:
    def __init__(self) -> None:
        self.base_output = config.OUTPUT_DIR
        self.base_json   = config.JSON_DIR
        self.base_photo  = config.PHOTO_DIR

    # ── 输出目录 ────────────────────────────────────────────────
    def get_output_dir(self, mode: str, name: str) -> str:
        """
        output/<mode>/<name>/
        blog / comment 模式下 name 通常为空字符串
        """
        self._check_mode(mode)
        path = os.path.join(self.base_output, mode, name) if name else os.path.join(self.base_output, mode)
        os.makedirs(path, exist_ok=True)
        return path

    # ── JSON 目录 ───────────────────────────────────────────────
    def get_json_dir(self, mode: str, name: str,
                     sub_dir: Optional[str] = None) -> str:
        """
        原版路径逻辑：
          blog      → json/blog/<sub or 'comments'>/
          tag       → json/tag/<name>/<sub or 'comments'>/
          collection→ json/collection/<name>/<sub or 'comments'>/
          comment   → json/<sub or 'comments'>/
          update    → json/update/<sub or 'comments'>/
          subscription→ json/subscription/<name or ''>/<sub>/
        """
        self._check_mode(mode)

        if mode == "blog":
            path = os.path.join(self.base_json, mode, sub_dir or "comments")
        elif mode in ("tag", "collection"):
            path = os.path.join(self.base_json, mode, name, sub_dir or "comments")
        elif mode == "comment":
            path = os.path.join(self.base_json, sub_dir or "comments")
        elif mode == "update":
            path = os.path.join(self.base_json, mode, sub_dir or "comments")
        else:
            # subscription 及其他
            parts = [self.base_json, mode]
            if name:
                parts.append(name)
            if sub_dir:
                parts.append(sub_dir)
            path = os.path.join(*parts)

        os.makedirs(path, exist_ok=True)
        return path

    # ── 图片目录 ───────────────────────────────────────────────
    def get_photo_dir(self, mode: str, name: str) -> str:
        """photo/<mode>/<name>/"""
        self._check_mode(mode)
        path = os.path.join(self.base_photo, mode, name) if name else os.path.join(self.base_photo, mode)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _check_mode(mode: str) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of {_VALID_MODES}"
            )


# 全局单例
path_manager = PathManager()
