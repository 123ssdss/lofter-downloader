"""
博客处理器
专门处理单个LOFTER博客帖子的下载和组织
"""
from typing import Dict, Any
from processors.base_processor import WorkflowCoordinator
from processors.blog_content_processor import BlogContentProcessor


class BlogProcessor(WorkflowCoordinator):
    """博客处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.blog_content_processor = BlogContentProcessor(client, debug)
    
    def create_post_meta(self, post_id: str, blog_id: str, blog_name: str = "") -> Dict[str, Any]:
        """创建帖子元数据对象"""
        return {
            "blogInfo": {
                "blogId": blog_id, 
                "blogName": blog_name
            },
            "postData": {
                "postView": {
                    "id": post_id
                }
            }
        }
    
    def process_single_blog_post(self, post_id: str, blog_id: str, blog_name: str = "",
                                download_comments: bool = True,
                                download_images: bool = True) -> Dict[str, Any]:
        """处理单个博客帖子"""
        try:
            self.logger.info(f"开始处理博客帖子: {post_id}")
            
            # 创建帖子元数据
            post_meta = self.create_post_meta(post_id, blog_id, blog_name)
            
            # 使用博客内容处理器处理帖子
            result = self.blog_content_processor.process_single_post(
                post_meta=post_meta,
                name="single_post",
                download_comments=download_comments,
                source_type="blog",
                name_prefix="",
                download_images=download_images
            )
            
            if result:
                self.logger.info(f"博客帖子 {post_id} 处理成功")
            else:
                self.logger.error(f"博客帖子 {post_id} 处理失败")
            
            return result
            
        except Exception as e:
            self.handle_error(e, f"处理博客帖子 {post_id}")
            return {}
    
    def process(self, post_id: str, blog_id: str, blog_name: str = "",
               download_comments: bool = True,
               download_images: bool = True) -> Dict[str, Any]:
        """处理博客帖子的主要接口"""
        try:
            if not post_id:
                return {"success": False, "error": "帖子ID不能为空"}
            
            if not blog_id:
                return {"success": False, "error": "博客ID不能为空"}
            
            self.logger.info(f"处理博客模式 - 帖子ID: {post_id} | 博客ID: {blog_id}")
            
            # 处理单个帖子
            result = self.process_single_blog_post(
                post_id, blog_id, blog_name, download_comments, download_images
            )
            
            if result:
                return {
                    "success": True,
                    "post_id": post_id,
                    "blog_id": blog_id,
                    "processed_files": result
                }
            else:
                return {
                    "success": False,
                    "post_id": post_id,
                    "blog_id": blog_id,
                    "error": "帖子处理失败"
                }
                
        except Exception as e:
            self.handle_error(e, f"博客处理 {post_id}")
            return {"success": False, "error": str(e)}