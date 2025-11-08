"""
评论处理器
专门处理评论数据的获取、格式化和保存
"""
import os
from typing import Dict, Any, List, Optional
from processors.base_processor import ContentProcessor
from utils.path_manager import path_manager
from config import GROUP_COMMENTS_BY_QUOTE


class CommentProcessor(ContentProcessor):
    """评论处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
    
    def format_single_comment(self, comment: Dict[str, Any], indent_level: int = 0, is_reply: bool = False) -> str:
        """格式化单个评论"""
        indent = "    " * indent_level
        author = comment.get("author", {}).get("blogNickName", "Unknown")
        content = comment.get('content', '').strip()
        publish_time = comment.get('publishTimeFormatted', '')
        like_count = comment.get('likeCount', 0)
        ip_location = comment.get('ipLocation', '')
        quote = comment.get('quote', '')
        replies = comment.get('replies', [])
        
        result = f"{indent}----------\n"
        
        # 使用不同的标签回复和主评论
        if is_reply:
            result += f"{indent}回复人：{author}\n"
        else:
            result += f"{indent}---------- 主评论 ----------\n"
        
        # 添加引用内容（主评论有引用时显示）
        if not is_reply and quote:
            result += f"{indent}引用：{quote}\n"
        
        result += f"{indent}内容：{content}\n"
        result += f"{indent}作者：{author}\n"
        result += f"{indent}时间：{publish_time}\n"
        result += f"{indent}点赞数：{like_count}\n"
        
        # 添加回复数（主评论有回复时显示）
        if not is_reply and replies:
            result += f"{indent}回复数：{len(replies)}\n"
        
        # 添加IP位置信息（如果有）
        if ip_location:
            result += f"{indent}IP属地：{ip_location}\n"
        
        return result
    
    def format_replies(self, replies: List[Dict[str, Any]], indent_level: int = 1) -> str:
        """格式化回复列表"""
        result = ""
        result += f"{'    ' * indent_level}---------- 回复列表 ----------\n"
        for idx, reply in enumerate(replies, 1):
            # 格式化回复，使用正确的缩进 - 回复是L2、L3等，取决于上下文
            result += f"{'    ' * indent_level}回复{idx}：\n"
            result += f"{'    ' * (indent_level + 1)}作者：{reply.get('author', {}).get('blogNickName', 'Unknown')}\n"
            result += f"{'    ' * (indent_level + 1)}时间：{reply.get('publishTimeFormatted', '')}\n"
            result += f"{'    ' * (indent_level + 1)}内容：{reply.get('content', '').strip()}\n"
            result += f"{'    ' * (indent_level + 1)}点赞数：{reply.get('likeCount', 0)}\n"
            
            # 添加IP位置信息（如果有）
            ip_location = reply.get('ipLocation', '')
            if ip_location:
                result += f"{'    ' * (indent_level + 1)}IP属地：{ip_location}\n"
            
            result += "\n"  # 每个回复后添加换行
        return result
    
    def group_comments_by_quote(self, comments_data: List[Dict[str, Any]]) -> tuple:
        """按引用内容分组评论"""
        grouped = {}
        non_quoted = []
        
        for comment in comments_data:
            quote = comment.get('quote', '').strip()
            if quote:
                if quote not in grouped:
                    grouped[quote] = []
                grouped[quote].append(comment)
            else:
                non_quoted.append(comment)
        
        return grouped, non_quoted
    
    def format_comments_recursive_v1(self, comments_data: List[Dict[str, Any]], indent_level: int = 0) -> str:
        """递归格式化评论和回复（原始格式）"""
        result = ""
        
        for idx, comment in enumerate(comments_data, 1):
            quote = comment.get('quote', '')
            
            # 添加引用（如果存在）
            if quote:
                result += f"----------({quote})----------\n"
                result += f"---------- (L{indent_level}-{idx})\n"
                result += self.format_single_comment(comment, indent_level, is_reply=False)
            else:
                result += f"---------- (L{indent_level}-{idx})\n"
                # 格式化主评论
                result += self.format_single_comment(comment, indent_level, is_reply=False)
            
            # 添加回复部分（如果有回复）
            replies = comment.get('replies', [])
            if replies:
                result += self.format_replies(replies, indent_level + 1)
            
            result += "\n"  # 每个评论块后添加换行
        
        return result
    
    def format_comments_recursive_v2(self, comments_data: List[Dict[str, Any]], indent_level: int = 0) -> str:
        """递归格式化评论和回复（新格式，按引用分组）"""
        result = ""
        
        # 按引用分组评论
        grouped_comments, non_quoted_comments = self.group_comments_by_quote(comments_data)
        
        # 处理分组评论（有引用的）
        for quote, comments_list in grouped_comments.items():
            result += f"----------({quote})----------\n"
            
            # 处理组中的每个评论
            for idx, comment in enumerate(comments_list, 1):
                result += f"---------- (L{indent_level}-{idx})\n"
                result += self.format_single_comment(comment, indent_level, is_reply=False)
                
                # 添加回复部分（如果有回复）
                replies = comment.get('replies', [])
                if replies:
                    result += self.format_replies(replies, indent_level + 1)
                
                result += "\n"  # 每个评论块后添加换行
        
        # 处理非引用评论
        for idx, comment in enumerate(non_quoted_comments, 1):
            result += f"---------- (L{indent_level}-{idx})\n"
            result += self.format_single_comment(comment, indent_level, is_reply=False)
            
            # 添加回复部分（如果有回复）
            replies = comment.get('replies', [])
            if replies:
                result += self.format_replies(replies, indent_level + 1)
            
            result += "\n"  # 每个评论块后添加换行
        
        return result
    
    def format_comments_recursive(self, comments_data: List[Dict[str, Any]], indent_level: int = 0) -> str:
        """递归格式化评论和回复，根据配置选择方法"""
        if GROUP_COMMENTS_BY_QUOTE:
            return self.format_comments_recursive_v2(comments_data, indent_level)
        else:
            return self.format_comments_recursive_v1(comments_data, indent_level)
    
    def process_comments_data(self, structured_comments: Dict[str, Any]) -> str:
        """处理评论数据并格式化"""
        try:
            # 检查返回的数据结构是新的还是旧的
            if isinstance(structured_comments, dict) and "hot_list" in structured_comments and "all_list" in structured_comments:
                # 新结构: 包含hot_list和all_list
                result = "[热门评论]\n"
                result += self.format_comments_recursive(structured_comments["hot_list"])
                result += "\n[全部评论]\n"
                result += self.format_comments_recursive(structured_comments["all_list"])
                return result
            else:
                # 旧结构: 直接处理列表
                return self.format_comments_recursive(structured_comments)
        except Exception as e:
            self.handle_error(e, "处理评论数据")
            return ""
    
    def process_post_comments(self, post_id: str, blog_id: str, mode: str = 'comment', name: str = '') -> str:
        """获取并格式化帖子的所有评论"""
        try:
            # 获取结构化评论数据
            structured_comments = self.client.fetch_all_comments_for_post(
                post_id, blog_id, return_structure=True, mode=mode, name=name
            )
            
            # 格式化评论数据
            return self.process_comments_data(structured_comments)
            
        except Exception as e:
            self.handle_error(e, f"获取帖子评论 {post_id}")
            return ""
    
    def save_comments_data(self, comments_text: str, mode: str, name: str, base_filename: str) -> str:
        """保存评论数据到文件"""
        try:
            comments_dir = path_manager.get_json_dir(mode, name, "comments")
            comments_file_path = os.path.join(comments_dir, f"{base_filename}_comments.txt")
            self.save_text_data(comments_text, comments_file_path)
            return comments_file_path
        except Exception as e:
            self.handle_error(e, f"保存评论数据 {base_filename}")
            return ""
    
    def process(self, post_id: str, blog_id: str, mode: str = 'comment', name: str = '', 
                save_to_file: bool = False, base_filename: str = "") -> str:
        """处理评论的主要接口"""
        comments_text = self.process_post_comments(post_id, blog_id, mode, name)
        
        if save_to_file and base_filename and comments_text:
            self.save_comments_data(comments_text, mode, name, base_filename)
        
        return comments_text