"""
评论模式处理器（重构版本）
专门处理单个帖子评论的模式
"""
import os
import re
import json
from datetime import datetime
from network import LofterClient
from utils.path_manager import path_manager
from processors.comment_processor_refactored import process_comments


class CommentModeProcessor:
    """评论模式处理器"""
    
    def __init__(self, client: LofterClient):
        """
        初始化处理器
        
        Args:
            client: LofterClient实例
        """
        self.client = client
    
    def process(self, post_url_or_id: str, blog_id: str = None):
        """
        处理评论模式
        
        Args:
            post_url_or_id: 帖子URL或ID
            blog_id: 博客ID（可选，如果提供URL则可能从URL中提取）
        """
        print(f"开始处理评论模式，帖子: {post_url_or_id}")
        
        # 解析帖子ID和博客ID
        post_id, blog_id = self._parse_post_info(post_url_or_id, blog_id)
        
        if not post_id:
            print("无法提取到有效的post_id")
            return
        
        if not blog_id:
            print("需要提供blog_id")
            return
        
        # 获取帖子详情
        post_detail = self.client.fetch_post_detail_by_id(post_id, blog_id)
        
        if not self._is_valid_post_detail(post_detail):
            print(f"无法获取帖子详情: {post_id}")
            return
        
        # 提取帖子信息
        post = post_detail["response"]["posts"][0]["post"]
        base_filename = self._create_safe_filename(post)
        
        # 保存帖子JSON数据
        self._save_post_json(post_detail, base_filename)
        
        # 获取并保存评论
        comments_text = process_comments(self.client, post_id, blog_id, mode='comment')
        self._save_comments_text(comments_text, base_filename)
        
        # 保存帖子内容
        self._save_post_content(post, base_filename, comments_text)
        
        print(f"评论模式处理完成: {base_filename}")
    
    def _parse_post_info(self, post_url_or_id: str, blog_id: str = None) -> tuple:
        """
        解析帖子信息
        
        Args:
            post_url_or_id: 帖子URL或ID
            blog_id: 博客ID
            
        Returns:
            (post_id, blog_id) 元组
        """
        if post_url_or_id.startswith('http'):
            post_id = self._extract_post_id_from_url(post_url_or_id)
            if not blog_id:
                blog_id = self._extract_blog_id_from_url(post_url_or_id)
        else:
            post_id = post_url_or_id
        
        return post_id, blog_id
    
    def _extract_post_id_from_url(self, url: str) -> str:
        """
        从URL中提取帖子ID
        
        Args:
            url: 帖子URL
            
        Returns:
            帖子ID或None
        """
        patterns = [
            r'/post/([a-zA-Z0-9]+)',
            r'/post/([a-zA-Z0-9]+)\?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_blog_id_from_url(self, url: str) -> str:
        """
        从URL中提取博客ID
        
        Args:
            url: 帖子URL
            
        Returns:
            博客ID或None
        """
        pattern = r'//(.*?)\.lofter\.com'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def _is_valid_post_detail(self, post_detail: dict) -> bool:
        """
        检查帖子详情是否有效
        
        Args:
            post_detail: 帖子详情数据
            
        Returns:
            是否有效
        """
        return (
            post_detail and 
            "response" in post_detail and 
            post_detail["response"].get("posts")
        )
    
    def _create_safe_filename(self, post: dict) -> str:
        """
        创建安全的文件名
        
        Args:
            post: 帖子数据
            
        Returns:
            安全的文件名
        """
        title = post.get("title", "Untitled")
        author = post["blogInfo"].get("blogNickName", "Unknown Author")
        
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
        safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
        
        return f"({safe_title} by {safe_author})"
    
    def _save_post_json(self, post_detail: dict, base_filename: str):
        """
        保存帖子JSON数据
        
        Args:
            post_detail: 帖子详情数据
            base_filename: 基础文件名
        """
        json_dir = path_manager.get_json_dir('comment', 'posts', 'blog')
        json_file_path = os.path.join(json_dir, f"{base_filename}.json")
        
        os.makedirs(json_dir, exist_ok=True)
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(post_detail, f, ensure_ascii=False, indent=4)
    
    def _save_comments_text(self, comments_text: str, base_filename: str):
        """
        保存评论文本
        
        Args:
            comments_text: 格式化的评论文本
            base_filename: 基础文件名
        """
        comments_dir = path_manager.get_json_dir('comment', 'posts', 'comments')
        comments_file_path = os.path.join(comments_dir, f"{base_filename}_comments.txt")
        
        os.makedirs(comments_dir, exist_ok=True)
        with open(comments_file_path, 'w', encoding='utf-8') as f:
            f.write(comments_text)
    
    def _save_post_content(self, post: dict, base_filename: str, comments_text: str):
        """
        保存帖子内容（包含评论）
        
        Args:
            post: 帖子数据
            base_filename: 基础文件名
            comments_text: 格式化的评论文本
        """
        output_dir = path_manager.get_output_dir('comment', 'posts')
        output_file_path = os.path.join(output_dir, f"{base_filename}.txt")
        
        PostContentFormatter.save_as_txt(post, output_file_path, comments_text)


class PostContentFormatter:
    """帖子内容格式化器"""
    
    @staticmethod
    def save_as_txt(post: dict, filepath: str, comments_text: str):
        """
        将帖子保存为TXT文件
        
        Args:
            post: 帖子数据
            filepath: 输出文件路径
            comments_text: 评论文本
        """
        import html
        
        title = post.get("title", "Untitled")
        publish_time = datetime.fromtimestamp(
            post["publishTime"] / 1000
        ).strftime('%Y-%m-%d %H:%M:%S')
        author = post["blogInfo"].get("blogNickName", "Unknown Author")
        blog_id = post["blogInfo"].get("blogId", "Unknown ID")
        blog_url = post.get("blogPageUrl", "")
        post_tags = ", ".join(post.get("tagList", []))
        
        # 转换内容
        content = ""
        if post.get("type") == 1:
            content = PostContentFormatter._convert_html_to_text(
                post.get("content", "")
            )
        elif post.get("type") == 2:
            content = "[Photo Post with potential images]"
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n")
            f.write(f"发布时间: {publish_time}\n")
            f.write(f"作者: {author}\n")
            f.write(f"作者LOFTERID: {blog_id}\n")
            f.write(f"Tags: {post_tags}\n")
            f.write(f"Link: {blog_url}\n\n")
            f.write("[正文]\n")
            f.write(content)
            f.write("\n\n\n\n")
            f.write("【评论】\n")
            if comments_text:
                f.write(comments_text)
            else:
                f.write("(暂无评论)\n")
    
    @staticmethod
    def _convert_html_to_text(html_content: str) -> str:
        """
        将HTML内容转换为纯文本
        
        Args:
            html_content: HTML内容
            
        Returns:
            纯文本内容
        """
        import html
        
        if not html_content:
            return ""
        
        text = html.unescape(html_content)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()


def process_comment_mode(client: LofterClient, post_url_or_id: str, blog_id: str = None):
    """
    处理评论模式（保持向后兼容的函数接口）
    
    Args:
        client: LofterClient实例
        post_url_or_id: 帖子URL或ID
        blog_id: 博客ID
    """
    processor = CommentModeProcessor(client)
    processor.process(post_url_or_id, blog_id)
