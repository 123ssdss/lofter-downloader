"""
src/models/post.py
帖子数据模型 — 简单的 dataclass，用于在层之间传递数据
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class PostMeta:
    """
    调用 API 所需的最小帖子定位信息。
    对应原始代码中的 post_meta 字典结构。
    """
    post_id:   str
    blog_id:   str
    blog_name: str = ""  # xxx.lofter.com 中的 xxx

    def to_api_dict(self) -> dict:
        """转换为 fetch_post_detail 所需的字典结构。"""
        return {
            "blogInfo": {
                "blogId":   self.blog_id,
                "blogName": self.blog_name,
            },
            "postData": {
                "postView": {
                    "id": self.post_id,
                }
            },
        }


@dataclass
class DownloadResult:
    """单个帖子下载完成后的结果汇总。"""
    post_id:       str
    base_filename: str
    success:       bool        = True
    json_file:     str         = ""
    text_file:     str         = ""
    photo_files:   List[str]   = field(default_factory=list)
    comments_file: str         = ""
    error:         str         = ""
