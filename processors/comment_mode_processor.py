"""
评论模式处理器
专门用于处理单个帖子评论的独立模式
"""
import re
from typing import Dict, Any, Optional
from processors.base_processor import WorkflowCoordinator
from processors.comment_processor import CommentProcessor
from processors.blog_content_processor import BlogContentProcessor


class CommentModeProcessor(WorkflowCoordinator):
    """评论模式处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.comment_processor = CommentProcessor(client, debug)
        self.blog_content_processor = BlogContentProcessor(client, debug)
    
    def extract_post_id_from_url(self, url: str) -> Optional[str]:
        """从URL中提取post_id"""
        patterns = [
            r'/post/([a-zA-Z0-9]+)',  # /post/postId
            r'/post/([a-zA-Z0-9]+)\?',  # /post/postId?param=value
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_blog_id_from_url(self, url: str) -> Optional[str]:
        """从URL中提取blog_id"""
        # 提取博客名称
        pattern = r'//(.*?)\.lofter\.com'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def parse_post_input(self, post_url_or_id: str, blog_id: Optional[str] = None) -> tuple:
        """解析帖子输入，返回(post_id, blog_id)"""
        if post_url_or_id.startswith('http'):
            # 从URL中提取post_id和blog_id
            post_id = self.extract_post_id_from_url(post_url_or_id)
            if not blog_id:
                blog_id = self.extract_blog_id_from_url(post_url_or_id)
        else:
            # 假设直接提供的是post_id
            post_id = post_url_or_id
        
        return post_id, blog_id
    
    def get_post_detail(self, post_id: str, blog_id: str) -> Dict[str, Any]:
        """获取帖子详细信息"""
        try:
            post_detail = self.client.fetch_post_detail_by_id(post_id, blog_id)
            
            if not post_detail or "response" not in post_detail or not post_detail["response"].get("posts"):
                self.logger.error(f"无法获取帖子详情: {post_id}")
                return {}
            
            return post_detail
            
        except Exception as e:
            self.handle_error(e, f"获取帖子详情 {post_id}")
            return {}
    
    def generate_base_filename(self, post_detail: Dict[str, Any]) -> str:
        """生成基础文件名"""
        try:
            post = post_detail["response"]["posts"][0]["post"]
            title = post.get("title", "Untitled")
            author = post["blogInfo"].get("blogNickName", "Unknown Author")
            
            # 创建安全的文件名
            safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
            safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
            base_filename = f"({safe_title} by {safe_author})"
            
            return base_filename
            
        except Exception as e:
            self.handle_error(e, "生成基础文件名")
            return f"post_{post_detail.get('id', 'unknown')}"
    
    def save_post_json(self, post_detail: Dict[str, Any], base_filename: str) -> str:
        """保存帖子JSON数据"""
        try:
            json_dir = path_manager.get_json_dir('comment', 'posts', 'blog')
            json_file_path = f"{json_dir}/{base_filename}.json"
            
            self.blog_content_processor.save_json_data(post_detail, json_file_path)
            return json_file_path
            
        except Exception as e:
            self.handle_error(e, f"保存帖子JSON {base_filename}")
            return ""
    
    def save_post_text(self, post_detail: Dict[str, Any], comments_text: str, base_filename: str) -> str:
        """保存帖子文本内容"""
        try:
            output_dir = path_manager.get_output_dir('comment', 'posts')
            output_file_path = f"{output_dir}/{base_filename}.txt"
            
            # 使用博客内容处理器格式化文本
            text_content = self.blog_content_processor.format_post_as_text(
                post_detail, comments_text=comments_text
            )
            
            self.blog_content_processor.save_text_data(text_content, output_file_path)
            return output_file_path
            
        except Exception as e:
            self.handle_error(e, f"保存帖子文本 {base_filename}")
            return ""
    
    def process(self, post_url_or_id: str, blog_id: Optional[str] = None) -> Dict[str, Any]:
        """处理评论模式的主要接口"""
        try:
            self.logger.info(f"开始处理评论模式，帖子: {post_url_or_id}")
            
            # 解析帖子输入
            post_id, extracted_blog_id = self.parse_post_input(post_url_or_id, blog_id)
            
            if not post_id:
                return {"success": False, "error": "无法提取到有效的post_id"}
            
            if not extracted_blog_id:
                return {"success": False, "error": "需要提供blog_id"}
            
            # 获取帖子详细信息
            post_detail = self.get_post_detail(post_id, extracted_blog_id)
            if not post_detail:
                return {"success": False, "error": f"无法获取帖子详情: {post_id}"}
            
            # 生成基础文件名
            base_filename = self.generate_base_filename(post_detail)
            
            # 保存帖子JSON数据
            json_file = self.save_post_json(post_detail, base_filename)
            
            # 获取评论
            comments_text = self.comment_processor.process_post_comments(
                post_id, extracted_blog_id, mode='comment'
            )
            
            # 保存评论到单独文件
            comments_file = ""
            if comments_text:
                comments_dir = path_manager.get_json_dir('comment', 'posts', 'comments')
                comments_file = f"{comments_dir}/{base_filename}_comments.txt"
                self.blog_content_processor.save_text_data(comments_text, comments_file)
            
            # 保存帖子内容到输出目录
            text_file = self.save_post_text(post_detail, comments_text, base_filename)
            
            result = {
                "success": True,
                "post_id": post_id,
                "blog_id": extracted_blog_id,
                "base_filename": base_filename,
                "json_file": json_file,
                "text_file": text_file,
                "comments_file": comments_file,
                "comments_count": len(comments_text.split('\n')) if comments_text else 0
            }
            
            self.logger.info(f"评论模式处理完成: {base_filename}")
            
            return result
            
        except Exception as e:
            self.handle_error(e, f"评论模式处理 {post_url_or_id}")
            return {"success": False, "error": str(e)}