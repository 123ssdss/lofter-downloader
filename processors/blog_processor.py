"""
博客处理器
专门处理单个LOFTER博客帖子的下载和组织
"""
from typing import Dict, Any
from processors.base_processor import WorkflowCoordinator
from processors.blog_content_processor import BlogContentProcessor
from utils.url_parser import parse_lofter_url, extract_blog_id_from_name, extract_ids_from_html
import requests


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
        """从URL或HTML内容中提取Blog ID和Post ID"""
        try:
            # 首先尝试解析URL
            url_info = parse_lofter_url(url)
            
            # 总是尝试从HTML中获取更多/更准确的信息，特别是当URL解析缺少blog_id时
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    html_content = response.text
                    html_info = extract_ids_from_html(html_content)
                    if html_info:
                        if html_info.get('blog_id') and html_info.get('post_id'):
                            # 如果从HTML中成功提取到完整ID，使用HTML中的信息
                            return {
                                'post_id': html_info['post_id'],
                                'blog_id': html_info['blog_id'],
                                'source': html_info.get('source', 'html_direct')
                            }
                        elif html_info.get('blog_id') and url_info and url_info.get('post_id'):
                            # 如果HTML中有blog_id但URL中有post_id，合并信息
                            result = url_info.copy() if url_info else {}
                            result['blog_id'] = html_info['blog_id']
                            result['source'] = html_info.get('source', 'html_merged')
                            return result
                        elif html_info.get('post_id'):
                            # 如果HTML中有post_id，使用HTML中的post_id
                            result = url_info.copy() if url_info else {}
                            result['post_id'] = html_info['post_id']
                            if html_info.get('blog_id'):
                                result['blog_id'] = html_info['blog_id']
                            result['source'] = html_info.get('source', 'html_post_id')
                            return result
            except Exception as e:
                self.logger.error(f"从URL获取HTML内容时出错: {e}")
                
            # 如果HTML解析失败或没有找到有用的信息，返回URL解析结果
            return url_info
                
        except Exception as e:
            self.logger.error(f"从URL提取ID时出错: {e}")
            
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
                    
                # 如果URL提供了blog_name，则尝试获取blog_id
                if not blog_id and url_info.get('blog_name'):
                    blog_name = url_info.get('blog_name')
                    # 尝试获取blog_id
                    extracted_blog_id = extract_blog_id_from_name(blog_name, self.client)
                    if extracted_blog_id:
                        blog_id = extracted_blog_id
                        self.logger.info(f"从博客名称 '{blog_name}' 提取到博客ID: {blog_id}")
                    else:
                        # 如果无法获取blog_id，但URL中包含blog_name，可以尝试其他方式
                        self.logger.warning(f"无法从博客名称 '{blog_name}' 获取博客ID，尝试使用其他方法")
            
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