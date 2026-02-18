"""
src/storage/image_downloader.py
图片下载模块 — 支持多线程并发下载（始终启用，线程数由 config.PHOTO_MAX_WORKERS 控制）。
"""
import os
import concurrent.futures
from typing import List, Optional
from urllib.parse import urlparse

import config


class ImageDownloader:
    """
    使用多线程下载图片列表。
    下载线程数固定为 config.PHOTO_MAX_WORKERS，不受帖子级 --threads 参数影响。
    """

    def __init__(self, client) -> None:
        """
        client: 实现了 download_photo(url, filepath) 方法的 API 客户端
        """
        self._client = client

    def download_all(self, urls: List[str], save_dir: str,
                     base_filename: str) -> List[str]:
        """
        并发下载所有 URL 到 save_dir/<base_filename> (N).<ext>。
        返回成功写入的文件路径列表。
        """
        if not urls:
            return []

        os.makedirs(save_dir, exist_ok=True)

        tasks: List[tuple] = []  # (url, filepath)
        for i, url in enumerate(urls):
            ext      = self._get_extension(url)
            filename = f"{base_filename} ({i + 1}){ext}"
            filepath = os.path.join(save_dir, filename)
            tasks.append((url, filepath))

        downloaded: List[str] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.PHOTO_MAX_WORKERS
        ) as executor:
            future_map = {
                executor.submit(self._client.download_photo, url, fp): (url, fp)
                for url, fp in tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                result = future.result()
                if result:
                    downloaded.append(result)

        return downloaded

    # ── 辅助方法 ────────────────────────────────────────────────

    @staticmethod
    def _get_extension(url: str) -> str:
        """从 URL 路径推断文件扩展名，默认 .jpg。"""
        path = urlparse(url).path
        ext  = os.path.splitext(path)[1].lower()
        return ext if ext else ".jpg"

    def build_url_to_local_map(self, urls: List[str], save_dir: str,
                               base_filename: str,
                               text_file_dir: str) -> dict:
        """
        为已下载的图片构造 {原始URL: 相对于 text_file_dir 的本地路径} 映射。
        用于在 .txt 文件中将原始 URL 替换为本地超链接。
        """
        url_map: dict = {}
        for i, url in enumerate(urls):
            ext      = self._get_extension(url)
            filename = f"{base_filename} ({i + 1}){ext}"
            filepath = os.path.join(save_dir, filename)
            if os.path.exists(filepath):
                rel = os.path.relpath(filepath, start=text_file_dir).replace("\\", "/")
                url_map[url] = f"[{filename}]({rel})"
        return url_map
