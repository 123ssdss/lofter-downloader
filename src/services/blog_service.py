"""
src/services/blog_service.py
博客/帖子服务 — 处理单个帖子的完整下载流程：
  获取详情 → 提取图片 → 下载图片 → 获取评论 → 保存 JSON / TXT
"""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import config
from src.core.api_client import LofterClient
from src.formatter import (
    build_post_filename,
    extract_post_metadata,
    format_post_as_text,
    make_safe_filename,
)
from src.logger import get_logger
from src.models.post import DownloadResult
from src.services.comment_service import CommentService
from src.storage.file_writer import FileWriter
from src.storage.image_downloader import ImageDownloader
from src.storage.path_manager import path_manager


class BlogService:
    """
    下载并保存单个帖子的全部内容。
    可被 TagService / CollectionService 复用。
    """

    def __init__(self, client: LofterClient, debug: bool = False) -> None:
        self._client   = client
        self._fw       = FileWriter()
        self._imgdl    = ImageDownloader(client)
        self._comment  = CommentService(client, debug)
        self._log      = get_logger("BlogService", debug)

    # ── 公开接口 ────────────────────────────────────────────────

    def download_post(
        self,
        post_meta:         dict,
        mode:              str,
        name:              str,
        download_comments: bool = False,
        download_images:   bool = True,
        filename_prefix:   str  = "",
    ) -> DownloadResult:
        """
        完整下载一个帖子。

        Args:
            post_meta:  API 所需的帖子定位字典
            mode:       'tag' | 'blog' | 'collection' | 'comment'
            name:       标签名 / 合集名（用于目录路径）
            download_comments: 是否下载评论
            download_images:   是否下载图片
            filename_prefix:   文件名前缀（合集模式用序号）
        """
        post_id = (post_meta.get("postData", {})
                            .get("postView", {})
                            .get("id", "unknown"))
        result  = DownloadResult(post_id=str(post_id), base_filename="")

        try:
            # 1. 获取帖子详情
            time.sleep(config.POST_DETAIL_REQUEST_DELAY)
            detail = self._client.fetch_post_detail(post_meta)
            if not self._is_valid_detail(detail):
                self._log.error(f"无法获取帖子详情: {post_id}")
                result.success = False
                result.error   = "fetch_post_detail 返回空"
                return result

            # 2. 构造文件名
            meta          = extract_post_metadata(detail)
            base_filename = build_post_filename(
                meta["title"], meta["author"],
                author_id=meta["blog_name"],
                prefix=filename_prefix,
            )
            result.base_filename = base_filename

            # 3. 保存原始 JSON
            json_dir  = path_manager.get_json_dir(mode, name, "blog")
            json_path = os.path.join(json_dir, f"{base_filename}.json")
            self._fw.write_json(detail, json_path)
            result.json_file = json_path

            # 4. 提取图片链接
            photo_links = self._extract_photo_links(detail)

            # 5. 下载图片
            photo_paths: List[str] = []
            if download_images and photo_links:
                photo_dir   = path_manager.get_photo_dir(mode, name)
                photo_paths = self._imgdl.download_all(
                    photo_links, photo_dir, base_filename
                )
            result.photo_files = photo_paths

            # 6. 获取评论（None = 未请求，"" = 请求了但无内容）
            comments_text = None
            if download_comments:
                post    = detail["response"]["posts"][0]["post"]
                bid     = str(post.get("blogInfo", {}).get("blogId", ""))
                pid     = str(post.get("id", post_id))
                if pid and bid:
                    comments_text = self._comment.fetch_and_save(
                        pid, bid, mode, name, base_filename
                    )
                    result.comments_file = os.path.join(
                        path_manager.get_json_dir(mode, name, "comments"),
                        f"{base_filename}_comments.txt",
                    )

            # 7. 生成并保存 .txt
            text_content = format_post_as_text(detail, photo_links, comments_text)

            # 在文本中将原始图片 URL 替换为本地相对路径超链接
            output_dir = path_manager.get_output_dir(mode, name)
            txt_path   = os.path.join(output_dir, f"{base_filename}.txt")
            if photo_paths and photo_links:
                photo_dir = path_manager.get_photo_dir(mode, name)
                url_map   = self._imgdl.build_url_to_local_map(
                    photo_links, photo_dir, base_filename,
                    text_file_dir=output_dir,
                )
                for orig_url, local_link in url_map.items():
                    text_content = text_content.replace(
                        orig_url, f"{orig_url} {local_link}"
                    )

            self._fw.write_text(text_content, txt_path)
            result.text_file = txt_path

            self._log.info(f"帖子保存完成: {base_filename}")
            return result

        except Exception as e:
            self._log.error(f"download_post 异常 post={post_id}: {e}")
            result.success = False
            result.error   = str(e)
            return result

    def download_post_by_id(
        self,
        post_id:           str,
        blog_id:           Optional[str],
        download_comments: bool = True,
        download_images:   bool = True,
    ) -> DownloadResult:
        """
        通过 post_id（或 URL）直接下载帖子（blog 模式入口）。
        支持 URL 输入（自动提取 ID）。
        """
        # 如果是 URL，先提取 ID
        if post_id.startswith("http"):
            extracted_post_id, extracted_blog_id = self._extract_ids_from_url(post_id)
            if not extracted_post_id:
                r = DownloadResult(post_id=post_id, base_filename="",
                                   success=False, error="无法从 URL 提取 post_id")
                return r
            post_id = extracted_post_id
            blog_id = blog_id or extracted_blog_id

        if not blog_id:
            r = DownloadResult(post_id=post_id, base_filename="",
                               success=False, error="需要提供 blog_id")
            return r

        detail = self._client.fetch_post_detail_by_id(post_id, blog_id)
        if not self._is_valid_detail(detail):
            r = DownloadResult(post_id=post_id, base_filename="",
                               success=False, error="fetch_post_detail_by_id 返回空")
            return r

        # 用 fetch_post_detail 的通用路径完成后续保存
        post_view = detail["response"]["posts"][0]["post"]
        blog_info = post_view.get("blogInfo", {})
        post_meta = {
            "blogInfo": {
                "blogId":   str(blog_info.get("blogId", blog_id)),
                "blogName": blog_info.get("blogName", ""),
            },
            "postData": {"postView": {"id": str(post_id)}},
        }
        # 复用已有详情，不重复请求
        return self._save_detail(
            detail=detail,
            post_meta=post_meta,
            mode="blog",
            name="",
            download_comments=download_comments,
            download_images=download_images,
            filename_prefix="",
        )

    # ── 内部方法 ────────────────────────────────────────────────

    def _save_detail(
        self,
        detail:            dict,
        post_meta:         dict,
        mode:              str,
        name:              str,
        download_comments: bool,
        download_images:   bool,
        filename_prefix:   str,
    ) -> DownloadResult:
        """将已获取的 detail 保存到磁盘（避免重复请求）。"""
        post_id = (post_meta.get("postData", {})
                            .get("postView", {})
                            .get("id", "unknown"))
        result  = DownloadResult(post_id=str(post_id), base_filename="")

        try:
            meta          = extract_post_metadata(detail)
            base_filename = build_post_filename(
                meta["title"], meta["author"],
                author_id=meta["blog_name"],
                prefix=filename_prefix,
            )
            result.base_filename = base_filename

            json_dir  = path_manager.get_json_dir(mode, name, "blog")
            json_path = os.path.join(json_dir, f"{base_filename}.json")
            self._fw.write_json(detail, json_path)
            result.json_file = json_path

            photo_links  = self._extract_photo_links(detail)
            photo_paths: List[str] = []
            if download_images and photo_links:
                photo_dir   = path_manager.get_photo_dir(mode, name)
                photo_paths = self._imgdl.download_all(
                    photo_links, photo_dir, base_filename
                )
            result.photo_files = photo_paths

            comments_text = None   # None = 未请求，"" = 请求了但无内容
            if download_comments:
                post = detail["response"]["posts"][0]["post"]
                bid  = str(post.get("blogInfo", {}).get("blogId", ""))
                pid  = str(post.get("id", post_id))
                if pid and bid:
                    comments_text = self._comment.fetch_and_save(
                        pid, bid, mode, name, base_filename
                    )

            text_content = format_post_as_text(detail, photo_links, comments_text)
            output_dir   = path_manager.get_output_dir(mode, name)
            txt_path     = os.path.join(output_dir, f"{base_filename}.txt")

            if photo_paths and photo_links:
                photo_dir = path_manager.get_photo_dir(mode, name)
                url_map   = self._imgdl.build_url_to_local_map(
                    photo_links, photo_dir, base_filename,
                    text_file_dir=output_dir,
                )
                for orig, local in url_map.items():
                    text_content = text_content.replace(orig, f"{orig} {local}")

            self._fw.write_text(text_content, txt_path)
            result.text_file = txt_path
            return result

        except Exception as e:
            self._log.error(f"_save_detail 异常 post={post_id}: {e}")
            result.success = False
            result.error   = str(e)
            return result

    @staticmethod
    def _is_valid_detail(detail: Optional[dict]) -> bool:
        return (detail is not None
                and "response" in detail
                and detail["response"].get("posts"))

    @staticmethod
    def _extract_photo_links(detail: dict) -> List[str]:
        """从帖子详情中提取所有图片 URL（含付费彩蛋图片）。"""
        try:
            post = detail["response"]["posts"][0]["post"]
            raw  = post.get("photoLinks", "[]")
            photos = json.loads(raw)
            links = [p.get("raw") or p.get("orign") for p in photos
                     if isinstance(p, dict)]

            # 付费彩蛋图片
            return_content = post.get("returnContent", [])
            if return_content:
                for img in return_content[0].get("images", []):
                    links.append(img)

            return [l for l in links if l]
        except Exception:
            return []

    def _extract_ids_from_url(self, url: str):
        """
        从帖子页面 HTML 中提取 post_id / blog_id。
        按用户要求：不再从 URL 正则提取，全部依赖 HTML 解析。
        """
        post_id = None
        blog_id = None

        # 使用浏览器 headers + Cookie 访问页面（在 fetch_html 内实现）
        html_content = self._client.fetch_html(url)
        if not html_content or not html_content.strip():
            self._log.error("从 URL 获取 HTML 失败，无法提取 post_id/blog_id")
            return None, None

        # 1) control_frame: ...control?blogId=123&postId=30b9c9c3
        m = re.search(
            r'<iframe[^>]*id=["\']control_frame["\'][^>]*src=["\'][^"\']*'
            r'lofter\.com/control\?blogId=(\d+)(?:&|&amp;)postId=([a-zA-Z0-9_]+)',
            html_content,
            flags=re.IGNORECASE,
        )
        if m:
            blog_id, post_id = m.group(1), m.group(2)
            return post_id, blog_id

        # 2) comment_frame: ...pid=30b9c9c3&bid=123
        m = re.search(
            r'<iframe[^>]*id=["\']comment_frame["\'][^>]*src=["\'][^"\']*'
            r'pid=([a-zA-Z0-9_]+)(?:&|&amp;)bid=(\d+)',
            html_content,
            flags=re.IGNORECASE,
        )
        if m:
            post_id, blog_id = m.group(1), m.group(2)
            return post_id, blog_id

        # 3) 内嵌 JSON: "blogId":123 / "postId":"30b9c9c3"
        m_blog = re.search(r'"blogId"\s*:\s*(\d+)', html_content)
        m_post = re.search(r'"postId"\s*:\s*"?([a-zA-Z0-9_]+)"?', html_content)
        if m_blog:
            blog_id = m_blog.group(1)
        if m_post:
            post_id = m_post.group(1)

        if post_id and blog_id:
            return post_id, blog_id

        self._log.error("HTML 解析失败：未找到有效的 post_id/blog_id")
        return None, None
