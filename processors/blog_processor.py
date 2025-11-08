"""
博客处理器
专门处理单个LOFTER博客帖子的下载和组织
"""
from typing import Dict, Any
from processors.base_processor import WorkflowCoordinator
from processors.blog_content_processor import BlogContentProcessor
from utils.url_parser import extract_ids_from_html


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
    
    def extract_ids_from_url(self, url: str) -> Dict[str, Any]:
        """从HTML内容或URL中提取Blog ID和Post ID"""
        try:
            # 总是尝试从HTML中获取信息
            try:
                # 使用LofterClient的fetch_html_content方法
                html_content = self.client.fetch_html_content(url, timeout=30)
                if html_content:
                    self.logger.info(f"成功获取HTML内容，长度: {len(html_content)}")
                    html_info = extract_ids_from_html(html_content, url)
                    if html_info:
                        self.logger.info(f"从HTML中成功提取信息: {html_info}")
                        return {
                            'post_id': html_info.get('post_id'),
                            'blog_id': html_info.get('blog_id'),
                            'blog_name': html_info.get('blog_name'),
                            'source': html_info.get('source', 'html_direct')
                        }
                    else:
                        self.logger.warning("从HTML中未找到有效的ID信息")
                else:
                    self.logger.warning("无法获取HTML内容")
            except Exception as e:
                self.logger.error(f"从URL获取HTML内容时出错: {e}")

            # HTML解析失败，无法提取ID信息
            self.logger.error("无法从HTML中提取ID信息")
            return None

        except Exception as e:
            self.logger.error(f"从URL提取ID时出错: {e}")
            return None

    def _test_with_sample_html(self, url: str) -> Dict[str, Any]:
        """使用示例HTML内容进行测试（用于演示功能）"""
        # 这个方法用于演示功能，当无法获取真实HTML时使用
        import os
        
        # 查找示例HTML文件
        sample_html_path = 'response_with_cookies.txt'
        if os.path.exists(sample_html_path):
            try:
                with open(sample_html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                self.logger.info(f"使用示例HTML文件进行测试: {sample_html_path}")
                html_info = extract_ids_from_html(html_content, url)
                if html_info:
                    self.logger.info(f"从示例HTML中成功提取信息: {html_info}")
                    return {
                        'post_id': html_info.get('post_id'),
                        'blog_id': html_info.get('blog_id'),
                        'blog_name': html_info.get('blog_name'),
                        'source': html_info.get('source', 'html_sample')
                    }
            except Exception as e:
                self.logger.error(f"读取示例HTML文件时出错: {e}")
        
        return None
    
    def process(self, post_id: str, blog_id: str, blog_name: str = "",
               download_comments: bool = True,
               download_images: bool = True) -> Dict[str, Any]:
        """处理博客帖子的主要接口"""
        try:
            # 检查post_id是否是URL
            if post_id and (post_id.startswith("http://") or post_id.startswith("https://")):
                # 从URL或HTML内容中提取ID
                url_info = self.extract_ids_from_url(post_id)
                if not url_info:
                    return {"success": False, "error": "无法解析Lofter URL或HTML内容"}
                
                # 提取post_id
                post_id = url_info.get('post_id')
                if not post_id:
                    return {"success": False, "error": "无法从URL或HTML中提取帖子ID"}
                
                # 尝试获取blog_id
                if not blog_id:
                    blog_id = url_info.get('blog_id')
                    
                # 如果URL提供了blog_name，则使用该名称
                if not blog_id and url_info.get('blog_name'):
                    blog_name = url_info.get('blog_name')
                    self.logger.info(f"从URL中获取到博客名称: {blog_name}")
                    # 注意：不再尝试通过名称获取博客ID，因为extract_blog_id_from_name方法已被移除
            
            if not post_id:
                return {"success": False, "error": "帖子ID不能为空"}
            
            # 注意：这里移除了对blog_id的强制检查，因为在某些情况下可能不需要blog_id
            # 但我们会记录警告
            if not blog_id:
                self.logger.warning("博客ID未提供，某些功能可能无法正常工作")
            
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