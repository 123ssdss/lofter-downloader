"""
基础处理器类
提供所有处理器的通用功能和接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import time
import logging
from utils.path_manager import path_manager
from utils.logger import BeautifulLogger


class BaseProcessor(ABC):
    """所有处理器的基类"""
    
    def __init__(self, client, debug: bool = False):
        self.client = client
        self.debug = debug
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        """设置美化日志记录器"""
        format_type = 'detailed' if self.debug else 'simple'
        logger = BeautifulLogger.setup_logger(
            name=self.__class__.__name__,
            level=logging.DEBUG if self.debug else logging.INFO,
            format_type=format_type,
            enable_color=True
        )
        return logger
    
    @abstractmethod
    def process(self, *args, **kwargs):
        """抽象处理方法，子类必须实现"""
        pass
    
    def handle_error(self, error: Exception, context: str = ""):
        """统一的错误处理"""
        error_msg = f"Error in {self.__class__.__name__}"
        if context:
            error_msg += f" during {context}"
        # 尝试安全地将异常转换为字符串，避免终端编码问题
        safe_error_str = str(error).encode('utf-8', 'replace').decode('utf-8')
        error_msg += f": {safe_error_str}"
        self.logger.error(error_msg)
        
    def safe_execute(self, func, *args, **kwargs):
        """安全执行函数，捕获异常"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle_error(e, func.__name__)
            return None


class ContentProcessor(BaseProcessor):
    """内容处理器基类"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.output_formatter = OutputFormatter()
    
    def process(self, *args, **kwargs):
        """默认实现，子类可以重写"""
        raise NotImplementedError("子类必须实现process方法")
        
    def save_json_data(self, data: Dict[str, Any], filepath: str):
        """保存JSON数据"""
        import json
        import os
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.logger.debug(f"JSON数据已保存到: {filepath}")
        except Exception as e:
            self.handle_error(e, f"保存JSON数据到 {filepath}")
    
    def save_text_data(self, content: str, filepath: str):
        """保存文本数据"""
        import os
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.debug(f"文本数据已保存到: {filepath}")
        except Exception as e:
            self.handle_error(e, f"保存文本数据到 {filepath}")


class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def format_post_filename(title: str, author: str, prefix: str = "", author_id: str = "") -> str:
        """格式化帖子文件名"""
        import re
        
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
        safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
        if author_id:
            base_filename = f"{safe_title} by {safe_author}[{author_id}]"
        else:
            base_filename = f"{safe_title} by {safe_author}"
        if prefix:
            base_filename = f"{prefix} {base_filename}"
        return base_filename
    
    @staticmethod
    def convert_html_to_text(html_content: str) -> str:
        """将HTML内容转换为纯文本"""
        if not html_content:
            return ""
        
        import html
        import re
        
        text = html.unescape(html_content)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    
    @staticmethod
    def extract_links_and_titles(html_content: str) -> str:
        """提取HTML中的链接和标题"""
        if not html_content:
            return ""
        
        import html
        import re
        
        # 先解码HTML实体
        text = html.unescape(html_content)
        
        # 定义替换函数，将链接替换为标题和链接的组合
        def replace_link(match):
            href, title = match.groups()
            # 清理标题中的HTML标签
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            # 返回格式化的链接信息
            return f"{clean_title} (链接: {href})"
        
        # 使用替换函数处理所有<a>标签
        processed_text = re.sub(r'<a\s+href\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a>', replace_link, text, flags=re.IGNORECASE | re.DOTALL)
        
        # 处理其他HTML标签
        processed_text = re.sub(r'<br\s*/?>', '\n', processed_text, flags=re.IGNORECASE)
        processed_text = re.sub(r'</p>', '\n\n', processed_text, flags=re.IGNORECASE)
        processed_text = re.sub(r'<[^>]+>', '', processed_text)
        
        return processed_text.strip()
    
    @staticmethod
    def format_post_metadata(post_data: Dict[str, Any]) -> Dict[str, str]:
        """格式化帖子元数据"""
        from datetime import datetime
        
        post = post_data.get("post", {})
        blog_info = post.get("blogInfo", {})
        
        title = post.get("title", "Untitled")
        publish_time = datetime.fromtimestamp(post.get("publishTime", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        author = blog_info.get("blogNickName", "Unknown Author")
        blog_id = blog_info.get("blogId", "Unknown ID")
        blog_name = blog_info.get("blogName", "Unknown Name")
        blog_url = post.get("blogPageUrl", "")
        post_tags = ", ".join(post.get("tagList", []))
        
        return {
            "title": title,
            "publish_time": publish_time,
            "author": author,
            "blog_id": blog_id,
            "blog_name": blog_name,
            "blog_url": blog_url,
            "tags": post_tags
        }


class MediaProcessor(BaseProcessor):
    """媒体处理器（图片等）"""
    
    def process(self, *args, **kwargs):
        """默认实现，子类可以重写"""
        raise NotImplementedError("子类必须实现process方法")
    
    def download_images(self, image_urls: List[str], save_dir: str, base_filename: str) -> List[str]:
        """下载图片列表"""
        if not image_urls:
            return []
        
        import os
        import concurrent.futures
        from urllib.parse import urlparse
        from config import PHOTO_MAX_WORKERS
        
        downloaded_paths = []
        
        if image_urls:
            os.makedirs(save_dir, exist_ok=True)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=PHOTO_MAX_WORKERS) as executor:
                future_to_url = {}
                for i, url in enumerate(image_urls):
                    extension = os.path.splitext(urlparse(url).path)[1].lower() or ".jpg"
                    filename = f"{base_filename} ({i+1}){extension}"
                    filepath = os.path.join(save_dir, filename)
                    future_to_url[executor.submit(self.client.download_photo, url, filepath)] = url

                for future in concurrent.futures.as_completed(future_to_url):
                    result = future.result()
                    if result:
                        downloaded_paths.append(result)
        
        return downloaded_paths


class WorkflowCoordinator(BaseProcessor):
    """工作流协调器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.content_processor = ContentProcessor(client, debug)
        self.media_processor = MediaProcessor(client, debug)
        self.comment_processor = None  # 延迟初始化
    
    def get_comment_processor(self):
        """获取评论处理器（延迟初始化）"""
        if self.comment_processor is None:
            from processors.comment_processor import CommentProcessor
            self.comment_processor = CommentProcessor(self.client, self.debug)
        return self.comment_processor
    
    def process_with_progress(self, items: List[Any], process_func, progress_name: str, *args, **kwargs):
        """带进度显示的处理"""
        from utils import display_progress
        import time
        
        total_items = len(items)
        if total_items == 0:
            self.logger.info(f"No items to process for {progress_name}")
            return
        
        self.logger.info(f"Processing {total_items} items for {progress_name}...")
        start_time = time.time()
        
        for i, item in enumerate(items):
            display_progress(i + 1, total_items, start_time, progress_name)
            try:
                process_func(item, *args, **kwargs)
            except Exception as e:
                self.handle_error(e, f"processing item {i+1} in {progress_name}")
        
        display_progress(total_items, total_items, start_time, f"{progress_name} Complete")
    
    def process_with_progress_with_results(self, items: List[Any], process_func, progress_name: str, *args, **kwargs):
        """带进度显示的处理，并收集结果"""
        from utils import display_progress
        import time
        
        total_items = len(items)
        if total_items == 0:
            self.logger.info(f"No items to process for {progress_name}")
            return []
        
        self.logger.info(f"Processing {total_items} items for {progress_name}...")
        start_time = time.time()
        results = []
        
        for i, item in enumerate(items):
            display_progress(i + 1, total_items, start_time, progress_name)
            try:
                result = process_func(item, i, *args, **kwargs)
                results.append(result)
            except Exception as e:
                self.handle_error(e, f"processing item {i+1} in {progress_name}")
                results.append((None, None))  # 添加空结果以保持一致性
        
        display_progress(total_items, total_items, start_time, f"{progress_name} Complete")
        return results