"""
src/services/comment_service.py
评论服务 — 获取、格式化、保存某个帖子的所有评论。
"""
import os
from typing import Optional

from src.core.api_client import LofterClient
from src.formatter import format_comments_block
from src.logger import get_logger
from src.storage.file_writer import FileWriter
from src.storage.path_manager import path_manager


class CommentService:
    """
    职责：
      1. 调用 API 获取结构化评论数据
      2. 格式化为文本
      3. 保存 JSON + 格式化 TXT 到磁盘
    """

    def __init__(self, client: LofterClient, debug: bool = False) -> None:
        self._client = client
        self._fw     = FileWriter()
        self._log    = get_logger("CommentService", debug)

    def fetch_and_save(
        self,
        post_id:  str,
        blog_id:  str,
        mode:     str,
        name:     str,
        base_filename: str,
    ) -> str:
        """
        获取帖子的全部评论，保存原始 JSON 和格式化 TXT，
        返回格式化后的评论文本（用于写入主 .txt 文件）。
        """
        try:
            structured = self._client.fetch_all_comments(post_id, blog_id)
            if not structured or (not structured.get("hot_list") and
                                  not structured.get("all_list")):
                return ""

            # 保存原始结构化 JSON
            json_dir  = path_manager.get_json_dir(mode, name, "comments")
            json_path = os.path.join(json_dir, f"comments_{post_id}_{blog_id}.json")
            self._fw.write_json(structured, json_path)

            # 格式化评论文本
            comments_text = format_comments_block(structured)

            # 保存格式化 TXT
            txt_path = os.path.join(json_dir, f"{base_filename}_comments.txt")
            self._fw.write_text(comments_text, txt_path)

            return comments_text

        except Exception as e:
            self._log.error(f"fetch_and_save 评论失败 post={post_id}: {e}")
            return ""

    def fetch_text_only(
        self,
        post_id: str,
        blog_id: str,
    ) -> str:
        """
        仅获取并格式化评论文本，不写入文件（用于 comment 模式）。
        """
        try:
            structured    = self._client.fetch_all_comments(post_id, blog_id)
            if not structured:
                return ""
            return format_comments_block(structured)
        except Exception as e:
            self._log.error(f"fetch_text_only 评论失败 post={post_id}: {e}")
            return ""
