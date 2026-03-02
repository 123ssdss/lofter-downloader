"""
src/services/collection_service.py
合集服务 — 获取合集元数据、批量下载所有帖子。
支持多线程（通过 post_workers 参数控制）。
"""
import concurrent.futures
import re
import time
from typing import Any, Dict, List

import config
from src.core.api_client import LofterClient
from src.logger import get_logger
from src.progress import ProgressBar
from src.services.blog_service import BlogService


class CollectionService:

    def __init__(self, client: LofterClient, debug: bool = False) -> None:
        self._client = client
        self._blog   = BlogService(client, debug)
        self._log    = get_logger("CollectionService", debug)

    def process(
        self,
        collection_id:     str,
        download_comments: bool = False,
        download_images:   bool = True,
        post_workers:      int  = 1,
    ) -> Dict[str, Any]:
        """
        下载合集中的全部帖子。

        Args:
            post_workers: 帖子级并发数（1 = 单线程）
        """
        self._log.info(f"获取合集 '{collection_id}' 元数据…")

        meta = self._get_metadata(collection_id)
        if not meta:
            return {"success": False, "error": f"无法获取合集 {collection_id} 元数据"}

        collection_name = meta["name"]
        post_count      = meta["post_count"]
        self._log.info(f"合集: '{collection_name}'，共 {post_count} 篇")

        if post_count == 0:
            return {"success": True, "collection_name": collection_name,
                    "total_posts": 0, "processed_posts": 0}

        # 分页获取所有帖子条目
        all_items = self._fetch_all_items(collection_id, post_count)
        if not all_items:
            return {"success": False, "error": "合集帖子列表为空"}

        self._log.info(f"开始下载 {len(all_items)} 篇帖子…")
        ok_count  = 0
        err_count = 0
        pb = ProgressBar(total=len(all_items), label=f"[{collection_name}]")
        pb.start()

        if post_workers <= 1:
            for i, item in enumerate(all_items):
                r = self._download_item(item, i, collection_name,
                                        download_comments, download_images)
                if r and r.success:
                    ok_count += 1
                else:
                    err_count += 1
                pb.update(i + 1)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=post_workers) as ex:
                futures = {
                    ex.submit(
                        self._download_item,
                        item, idx, collection_name,
                        download_comments, download_images
                    ): idx
                    for idx, item in enumerate(all_items)
                }
                done = 0
                for future in concurrent.futures.as_completed(futures):
                    r = future.result()
                    if r and r.success:
                        ok_count += 1
                    else:
                        err_count += 1
                    done += 1
                    pb.update(done)

        pb.finish()
        self._log.info(
            f"合集 '{collection_name}' 完成: {ok_count}/{len(all_items)} 成功"
        )
        return {
            "success":         True,
            "collection_name": collection_name,
            "total_posts":     len(all_items),
            "processed_posts": ok_count,
            "failed_posts":    err_count,
        }

    # ── 内部方法 ────────────────────────────────────────────────

    def _get_metadata(self, collection_id: str) -> Dict[str, Any]:
        resp = self._client.get_collection_list(collection_id, offset=0, limit=1)
        if not resp or "collection" not in resp:
            return {}

        info = resp["collection"]
        raw_name = info.get("name", "") or f"collection_{collection_id}"
        return {
            "id":         info.get("id", collection_id),
            "name":       self._safe_name(str(raw_name)),
            "post_count": info.get("postCount", 0),
            "blog_id":    info.get("blogId", ""),
        }

    def _fetch_all_items(self, collection_id: str, post_count: int) -> List[dict]:
        limit     = 50
        all_items: List[dict] = []

        for offset in range(0, post_count, limit):
            self._log.info(f"  获取帖子 {offset+1}–{min(offset+limit, post_count)}…")
            resp = self._client.get_collection_list(
                collection_id, offset=offset, limit=limit
            )
            if resp and "items" in resp:
                all_items.extend(resp["items"])
            time.sleep(config.COLLECTION_REQUEST_DELAY)

        return all_items

    def _download_item(self, item: dict, index: int, collection_name: str,
                       download_comments: bool, download_images: bool):
        """将合集 item 结构适配为 BlogService 所需的 post_meta 并下载。"""
        try:
            post_data  = item.get("post", {})
            blog_info  = item.get("blogInfo", {})
            if "blogInfo" in post_data:
                blog_info = post_data["blogInfo"]

            post_meta = {
                "blogInfo":  blog_info,
                "postData":  {"postView": post_data},
            }
            return self._blog.download_post(
                post_meta=post_meta,
                mode="collection",
                name=collection_name,
                download_comments=download_comments,
                download_images=download_images,
                filename_prefix=str(index + 1),
            )
        except Exception as e:
            self._log.error(f"下载合集帖子 index={index} 失败: {e}")
            return None

    @staticmethod
    def _safe_name(name: str) -> str:
        safe = re.sub(r'[\\/*?:"<>|]', "_", name)
        safe = safe.encode("utf-8", "ignore").decode("utf-8")
        return safe.strip() or "Unknown_Collection"
