"""
src/models/comment.py
评论数据模型
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Reply:
    """L2 回复（评论的评论）"""
    id:                   str
    content:              str
    author_nick:          str
    author_blog_name:     str
    publish_time:         int    = 0
    publish_time_str:     str    = ""
    like_count:           int    = 0
    ip_location:          str    = ""
    quote:                str    = ""
    emotes:               list   = field(default_factory=list)
    reply_to:             dict   = field(default_factory=dict)


@dataclass
class Comment:
    """L1 评论（帖子的直接评论）"""
    id:                   str
    content:              str
    author_nick:          str
    author_blog_name:     str
    publish_time:         int    = 0
    publish_time_str:     str    = ""
    like_count:           int    = 0
    ip_location:          str    = ""
    quote:                str    = ""
    emotes:               list   = field(default_factory=list)
    is_hot:               bool   = False
    replies:              List[Reply] = field(default_factory=list)


@dataclass
class CommentsData:
    """一个帖子的全部评论，分热门和全部两个列表（与原版结构对应）"""
    hot_list: List[dict]  = field(default_factory=list)  # 已归一化的 dict
    all_list: List[dict]  = field(default_factory=list)  # 已归一化的 dict

    def to_dict(self) -> dict:
        return {"hot_list": self.hot_list, "all_list": self.all_list}
