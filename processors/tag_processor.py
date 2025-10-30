"""
标签处理器
专门处理LOFTER标签的内容下载和组织
"""
from typing import Dict, Any, List
from processors.base_processor import WorkflowCoordinator
from processors.blog_content_processor import BlogContentProcessor
from config import TAG_POST_REQUEST_DELAY


class TagProcessor(WorkflowCoordinator):
    """标签处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.blog_processor = BlogContentProcessor(client, debug)
    
    def fetch_posts_by_tag(self, tag: str, list_type: str = "total", 
                          timelimit: str = "", blog_type: str = "1") -> List[Dict[str, Any]]:
        """根据标签获取帖子列表"""
        try:
            posts = self.client.fetch_posts_by_tag(tag, list_type, timelimit, blog_type)
            self.logger.info(f"标签 '{tag}' 找到 {len(posts)} 个帖子")
            return posts
        except Exception as e:
            self.handle_error(e, f"获取标签帖子 {tag}")
            return []
    
    def process_single_tag_post(self, post_meta: Dict[str, Any], tag: str,
                               download_comments: bool = False,
                               download_images: bool = True) -> Dict[str, Any]:
        """处理标签中的单个帖子"""
        try:
            # 使用博客内容处理器处理帖子
            result = self.blog_processor.process_single_post(
                post_meta=post_meta,
                name=tag,
                download_comments=download_comments,
                source_type="tag-tag",
                name_prefix="",
                download_images=download_images
            )
            
            return result
            
        except Exception as e:
            post_id = post_meta.get('postData', {}).get('postView', {}).get('id', 'Unknown')
            self.handle_error(e, f"处理标签帖子 {post_id}")
            return {}
    
    def process_single_tag(self, tag: str, list_type: str = "total",
                          timelimit: str = "", blog_type: str = "1",
                          download_comments: bool = False,
                          download_images: bool = True) -> Dict[str, Any]:
        """处理单个标签"""
        try:
            self.logger.info(f"开始处理标签 '{tag}'...")
            
            # 获取标签下的帖子
            posts = self.fetch_posts_by_tag(tag, list_type, timelimit, blog_type)
            
            if not posts:
                self.logger.info(f"标签 '{tag}' 没有找到帖子")
                return {"success": True, "message": f"标签 '{tag}' 没有找到帖子"}
            
            # 处理所有帖子
            processed_posts = []
            failed_posts = []
            
            def process_post_with_delay(post_meta, index):
                try:
                    result = self.process_single_tag_post(
                        post_meta, tag, download_comments, download_images
                    )
                    
                    # 添加请求延迟
                    import time
                    time.sleep(TAG_POST_REQUEST_DELAY)
                    
                    if result:
                        return result
                    else:
                        post_id = post_meta.get('postData', {}).get('postView', {}).get('id', 'Unknown')
                        return (None, post_id)
                    
                except Exception as e:
                    post_id = post_meta.get('postData', {}).get('postView', {}).get('id', 'Unknown')
                    self.handle_error(e, f"处理标签帖子 {post_id}")
                    return (None, post_id)
            
            # 使用工作流协调器处理进度并收集结果
            results = self.process_with_progress_with_results(
                posts,
                process_post_with_delay,
                f"Tag '{tag}'"
            )
            
            # 处理结果
            for result in results:
                if isinstance(result, tuple) and len(result) == 2 and result[0] is None:
                    # 失败的情况
                    failed_posts.append(result[1])
                elif result:
                    # 成功的情况
                    processed_posts.append(result)
            
            # 返回处理结果
            result = {
                "success": True,
                "tag_name": tag,
                "list_type": list_type,
                "timelimit": timelimit,
                "blog_type": blog_type,
                "total_posts": len(posts),
                "processed_posts": len(processed_posts),
                "failed_posts": len(failed_posts),
                "failed_post_ids": failed_posts
            }
            
            self.logger.info(f"标签 '{tag}' 处理完成: {len(processed_posts)}/{len(posts)} 成功")
            
            return result
            
        except Exception as e:
            self.handle_error(e, f"处理标签 {tag}")
            return {"success": False, "error": str(e)}
    
    def process(self, tags: List[str], list_type: str = "total",
               timelimit: str = "", blog_type: str = "1",
               download_comments: bool = False,
               download_images: bool = True) -> Dict[str, Any]:
        """处理多个标签的主要接口"""
        try:
            if not tags:
                return {"success": False, "error": "没有提供标签"}
            
            self.logger.info(f"开始处理 {len(tags)} 个标签: {tags}")
            
            all_results = {}
            total_processed = 0
            total_failed = 0
            
            for tag in tags:
                if not tag:  # 跳过空标签
                    continue
                
                result = self.process_single_tag(
                    tag, list_type, timelimit, blog_type,
                    download_comments, download_images
                )
                
                all_results[tag] = result
                
                if result.get("success"):
                    total_processed += result.get("processed_posts", 0)
                    total_failed += result.get("failed_posts", 0)
                else:
                    self.logger.error(f"标签 '{tag}' 处理失败: {result.get('error', 'Unknown error')}")
            
            # 返回总体处理结果
            final_result = {
                "success": True,
                "total_tags": len([t for t in tags if t]),
                "processed_tags": len([t for t in tags if t and all_results.get(t, {}).get("success")]),
                "total_posts_processed": total_processed,
                "total_posts_failed": total_failed,
                "tag_results": all_results
            }
            
            self.logger.info(f"所有标签处理完成: {final_result['processed_tags']}/{final_result['total_tags']} 标签成功")
            
            return final_result
            
        except Exception as e:
            self.handle_error(e, "处理标签列表")
            return {"success": False, "error": str(e)}