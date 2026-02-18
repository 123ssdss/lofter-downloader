"""
src/services/subscription_service.py
订阅服务 — 获取并保存用户订阅的合集列表。
"""
import os
from typing import Any, Dict, List

from src.core.api_client import LofterClient
from src.logger import get_logger
from src.storage.file_writer import FileWriter
from src.storage.path_manager import path_manager


class SubscriptionService:

    def __init__(self, client: LofterClient, debug: bool = False) -> None:
        self._client = client
        self._fw     = FileWriter()
        self._log    = get_logger("SubscriptionService", debug)

    def process(self) -> Dict[str, Any]:
        """
        获取所有订阅合集，保存为：
          - output/subscription.txt  （人类可读格式）
          - json/subscription.json   （原始 JSON）
        """
        self._log.info("开始获取订阅列表…")

        collections = self._client.fetch_subscription_collections()
        if not collections:
            return {"success": False, "message": "没有获取到订阅数据或订阅列表为空"}

        total = len(collections)
        self._log.info(f"共 {total} 个订阅合集")

        # ── 保存 JSON ─────────────────────────────────────────
        json_path = os.path.join("json", "subscription.json")
        os.makedirs("json", exist_ok=True)
        self._fw.write_json(collections, json_path)

        # ── 保存人类可读 TXT ──────────────────────────────────
        txt_path = os.path.join("output", "subscription.txt")
        os.makedirs("output", exist_ok=True)
        txt_content = self._format_txt(collections, total)
        self._fw.write_text(txt_content, txt_path)

        self._log.info(f"订阅列表已保存: {txt_path} / {json_path}")

        return {
            "success":            True,
            "total_subscriptions": total,
            "total_unread":        sum(c.get("unreadCount", 0) for c in collections),
            "txt_file":           txt_path,
            "json_file":          json_path,
        }

    @staticmethod
    def _format_txt(collections: List[dict], total: int) -> str:
        lines = [f"订阅总数: {total}", "=" * 50]
        for c in collections:
            if not c.get("valid", True):
                continue
            lines.append(f"合集名：{c.get('name', '')}")
            lines.append(f"合集ID：{c.get('collectionId', '')}")
            author = c.get("blogInfo", {}).get("blogNickName", "")
            if author:
                lines.append(f"作者：{author}")
            url = c.get("collectionUrl", "")
            if url:
                lines.append(f"链接：{url}")
            lines.append("-" * 30)
        return "\n".join(lines)
