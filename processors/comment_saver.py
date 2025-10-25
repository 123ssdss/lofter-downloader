"""
评论保存模块
负责将评论数据保存到文件系统
"""
import os
import json
from typing import Dict
from utils.path_manager import path_manager


class CommentSaver:
    """评论保存器，负责将评论数据保存到不同格式的文件"""
    
    def __init__(self, client):
        """
        初始化评论保存器
        
        Args:
            client: LofterClient实例（用于日志记录）
        """
        self.client = client
    
    def save_comments(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str = 'comment', 
        name: str = ''
    ):
        """
        保存评论到文件系统
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            structured_comments: 结构化的评论数据
            mode: 模式 ('tag', 'collection', 'blog', 'comment', 'subscription')
            name: 名称（标签名、收藏集名等）
        """
        # 保存JSON格式的原始数据
        self._save_as_json(post_id, blog_id, structured_comments, mode, name)
        
        # 保存用户格式的简化文本
        self._save_user_format(post_id, blog_id, structured_comments, mode, name)
    
    def _save_as_json(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str, 
        name: str
    ):
        """
        保存为JSON格式
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            structured_comments: 结构化的评论数据
            mode: 模式
            name: 名称
        """
        try:
            json_dir = self._get_json_dir(mode, name)
            filename = f"comments_{post_id}_{blog_id}.json"
            filepath = os.path.join(json_dir, filename)
            
            os.makedirs(json_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(structured_comments, f, ensure_ascii=False, indent=2)
            
            self.client._log(f"JSON评论已保存: {filepath}")
            
        except Exception as e:
            self.client._log(f"保存JSON评论时出错: {e}")
    
    def _save_user_format(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str, 
        name: str
    ):
        """
        保存为用户格式（简化的文本格式）
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            structured_comments: 结构化的评论数据
            mode: 模式
            name: 名称
        """
        try:
            json_dir = self._get_json_dir(mode, name)
            filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            filepath = os.path.join(json_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                all_comments = structured_comments.get("all_list", [])
                
                for comment in all_comments:
                    comment_id = comment.get("id", "unknown")
                    content = comment.get("content", "")
                    f.write(f"[l1 {comment_id}]\n")
                    f.write(f"{content}\n")
                    
                    # 处理L2回复
                    replies = comment.get("replies", [])
                    for reply in replies:
                        reply_id = reply.get("id", "unknown")
                        reply_content = reply.get("content", "")
                        f.write(f"   [l2 {reply_id}]\n")
                        f.write(f"    {reply_content}\n")
                    
                    f.write("\n")
            
            self.client._log(f"用户格式评论已保存: {filepath}")
            
        except Exception as e:
            self.client._log(f"保存用户格式评论时出错: {e}")
    
    def _get_json_dir(self, mode: str, name: str) -> str:
        """
        根据模式获取JSON目录
        
        Args:
            mode: 模式
            name: 名称
            
        Returns:
            JSON目录路径
        """
        mode_dir_map = {
            'blog': lambda: path_manager.get_json_dir('blog', name or '', 'comments'),
            'tag': lambda: path_manager.get_json_dir('tag', name or 'default_tag_name', 'comments'),
            'collection': lambda: path_manager.get_json_dir('collection', name or 'default_collection_name', 'comments'),
            'comment': lambda: path_manager.get_json_dir('comment', name or '', 'comments'),
            'subscription': lambda: path_manager.get_json_dir('subscription', name or '', 'comments'),
            'update': lambda: path_manager.get_json_dir('update', name or '', 'comments')
        }
        
        return mode_dir_map.get(mode, mode_dir_map['comment'])()
