"""
src/services/tag_service.py
标签服务 — 获取标签下所有帖子并批量下载。
支持多线程（通过 post_workers 参数控制）。
"""
import concurrent.futures
import os
import time
from typing import Any, Dict, List

import config
from src.core.api_client import LofterClient
from src.logger import get_logger
from src.progress import ProgressBar
from src.services.blog_service import BlogService
from src.storage.file_writer import FileWriter
from src.storage.path_manager import path_manager


class TagService:

    def __init__(self, client: LofterClient, debug: bool = False) -> None:
        self._client = client
        self._blog   = BlogService(client, debug)
        self._fw     = FileWriter()
        self._log    = get_logger("TagService", debug)

    def process(
        self,
        tags:              List[str],
        list_type:         str  = None,
        timelimit:         str  = None,
        blog_type:         str  = None,
        download_comments: bool = False,
        download_images:   bool = True,
        post_workers:      int  = 1,
    ) -> Dict[str, Any]:
        """
        处理一批标签（每个标签独立下载）。

        Args:
            post_workers: 每个标签内的帖子并发处理数（1 = 单线程）
        """
        all_tag_results: Dict[str, dict] = {}
        total_ok  = 0
        total_err = 0

        for tag in tags:
            if not tag:
                continue
            res = self._process_single_tag(
                tag, list_type, timelimit, blog_type,
                download_comments, download_images, post_workers,
            )
            all_tag_results[tag] = res
            total_ok  += res.get("processed", 0)
            total_err += res.get("failed",    0)

        return {
            "success":             True,
            "total_tags":          len([t for t in tags if t]),
            "processed_tags":      sum(1 for r in all_tag_results.values() if r.get("success")),
            "total_posts_processed": total_ok,
            "total_posts_failed":    total_err,
            "tag_results":         all_tag_results,
        }

    # ── 内部方法 ────────────────────────────────────────────────

    def _process_single_tag(
        self,
        tag:               str,
        list_type:         str,
        timelimit:         str,
        blog_type:         str,
        download_comments: bool,
        download_images:   bool,
        post_workers:      int,
    ) -> dict:
        self._log.info(f"开始处理标签 '{tag}'…")

        posts = self._client.fetch_posts_by_tag(
            tag, list_type, timelimit, blog_type
        )

        # 保存标签原始响应 JSON
        self._save_tag_raw_json(tag)

        if not posts:
            self._log.info(f"标签 '{tag}' 无帖子")
            return {"success": True, "tag": tag, "total": 0, "processed": 0, "failed": 0}

        self._log.info(f"标签 '{tag}' 共 {len(posts)} 篇，开始下载…")
        ok_count  = 0
        err_count = 0
        pb = ProgressBar(total=len(posts), label=f"[{tag}]")
        pb.start()

        if post_workers <= 1:
            # 单线程
            for i, post_meta in enumerate(posts):
                r = self._download_one(post_meta, tag, download_comments, download_images)
                if r.success:
                    ok_count += 1
                else:
                    err_count += 1
                time.sleep(config.TAG_POST_REQUEST_DELAY)
                pb.update(i + 1)
        else:
            # 多线程
            with concurrent.futures.ThreadPoolExecutor(max_workers=post_workers) as ex:
                futures = {
                    ex.submit(
                        self._download_one,
                        pm, tag, download_comments, download_images
                    ): idx
                    for idx, pm in enumerate(posts)
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
        self._log.info(f"标签 '{tag}' 完成: {ok_count} 成功 / {err_count} 失败")

        return {
            "success":   True,
            "tag":       tag,
            "total":     len(posts),
            "processed": ok_count,
            "failed":    err_count,
        }

    def _download_one(self, post_meta, tag, download_comments, download_images):
        return self._blog.download_post(
            post_meta=post_meta,
            mode="tag",
            name=tag,
            download_comments=download_comments,
            download_images=download_images,
        )

    def _save_tag_raw_json(self, tag: str) -> None:
        """保存标签全部分页响应（用于存档）。"""
        try:
            pages = getattr(self._client, "_last_tag_pages", None)
            if not pages:
                return
            json_dir  = os.path.join(path_manager.base_json, "tag", tag)
            os.makedirs(json_dir, exist_ok=True)
            filepath  = os.path.join(json_dir, "tagresponse.json")
            self._fw.write_json(pages, filepath)
        except Exception as e:
            self._log.warning(f"保存标签原始响应失败: {e}")
