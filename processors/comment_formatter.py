"""
评论格式化模块
负责将评论数据格式化为可读文本
"""
from typing import Dict, List, Tuple
from config import GROUP_COMMENTS_BY_QUOTE


class CommentFormatter:
    """评论格式化器，负责将评论数据格式化为文本输出"""
    
    def format_comments(self, structured_comments: Dict) -> str:
        """
        格式化评论为文本
        
        Args:
            structured_comments: 包含hot_list和all_list的评论结构
            
        Returns:
            格式化后的评论文本
        """
        if not structured_comments:
            return ""
        
        result = "[热门评论]\n"
        result += self._format_comment_list(structured_comments.get("hot_list", []))
        result += "\n[全部评论]\n"
        result += self._format_comment_list(structured_comments.get("all_list", []))
        
        return result
    
    def _format_comment_list(self, comments: List[Dict]) -> str:
        """
        格式化评论列表
        
        Args:
            comments: 评论列表
            
        Returns:
            格式化后的文本
        """
        if GROUP_COMMENTS_BY_QUOTE:
            return self._format_comments_grouped_by_quote(comments)
        else:
            return self._format_comments_in_order(comments)
    
    def _format_comments_grouped_by_quote(self, comments: List[Dict]) -> str:
        """
        按引用内容分组格式化评论
        
        Args:
            comments: 评论列表
            
        Returns:
            格式化后的文本
        """
        grouped, non_quoted = self._group_comments_by_quote(comments)
        result = ""
        
        # 处理有引用的评论组
        for quote, comments_list in grouped.items():
            result += f"----------({quote})----------\n"
            for idx, comment in enumerate(comments_list, 1):
                result += f"---------- (L0-{idx})\n"
                result += self._format_single_comment(comment, indent_level=0)
                result += self._format_replies(comment.get("replies", []), indent_level=1)
                result += "\n"
        
        # 处理无引用的评论
        for idx, comment in enumerate(non_quoted, 1):
            result += f"---------- (L0-{idx})\n"
            result += self._format_single_comment(comment, indent_level=0)
            result += self._format_replies(comment.get("replies", []), indent_level=1)
            result += "\n"
        
        return result
    
    def _format_comments_in_order(self, comments: List[Dict]) -> str:
        """
        按原始顺序格式化评论
        
        Args:
            comments: 评论列表
            
        Returns:
            格式化后的文本
        """
        result = ""
        
        for idx, comment in enumerate(comments, 1):
            quote = comment.get('quote', '')
            
            if quote:
                result += f"----------({quote})---------- (L0-{idx})\n"
            else:
                result += f"---------- (L0-{idx})\n"
            
            result += self._format_single_comment(comment, indent_level=0)
            result += self._format_replies(comment.get("replies", []), indent_level=1)
            result += "\n"
        
        return result
    
    def _format_single_comment(self, comment: Dict, indent_level: int = 0) -> str:
        """
        格式化单个评论
        
        Args:
            comment: 评论数据
            indent_level: 缩进级别
            
        Returns:
            格式化后的评论文本
        """
        indent = "    " * indent_level
        author = comment.get("author", {}).get("blogNickName", "Unknown")
        content = comment.get('content', '').strip()
        publish_time = comment.get('publishTimeFormatted', '')
        like_count = comment.get('likeCount', 0)
        ip_location = comment.get('ipLocation', '')
        
        result = f"{indent}----------\n"
        result += f"{indent}发布人：{author}\n"
        result += f"{indent}内容：{content}\n"
        result += f"{indent}时间：{publish_time}\n"
        result += f"{indent}点赞数：{like_count}\n"
        
        if ip_location:
            result += f"{indent}IP位置：{ip_location}\n"
        
        return result
    
    def _format_replies(self, replies: List[Dict], indent_level: int = 1) -> str:
        """
        格式化回复列表
        
        Args:
            replies: 回复列表
            indent_level: 缩进级别
            
        Returns:
            格式化后的回复文本
        """
        if not replies:
            return ""
        
        result = f"{'    ' * indent_level}---回复列表---\n"
        
        for idx, reply in enumerate(replies, 1):
            result += f"{'    ' * indent_level}---------- (L{indent_level + 1}-{idx})\n"
            result += f"{'    ' * (indent_level + 1)}回复人：{reply.get('author', {}).get('blogNickName', 'Unknown')}\n"
            result += f"{'    ' * (indent_level + 1)}内容：{reply.get('content', '').strip()}\n"
            result += f"{'    ' * (indent_level + 1)}时间：{reply.get('publishTimeFormatted', '')}\n"
            result += f"{'    ' * (indent_level + 1)}点赞数：{reply.get('likeCount', 0)}\n"
            result += "\n"
        
        return result
    
    def _group_comments_by_quote(self, comments: List[Dict]) -> Tuple[Dict, List]:
        """
        按引用内容分组评论
        
        Args:
            comments: 评论列表
            
        Returns:
            (分组的评论字典, 无引用的评论列表)
        """
        grouped = {}
        non_quoted = []
        
        for comment in comments:
            quote = comment.get('quote', '').strip()
            if quote:
                if quote not in grouped:
                    grouped[quote] = []
                grouped[quote].append(comment)
            else:
                non_quoted.append(comment)
        
        return grouped, non_quoted
