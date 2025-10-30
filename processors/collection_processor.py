"""
合集处理器
专门处理LOFTER合集的内容下载和组织
"""
import re
from typing import Dict, Any, List
from processors.base_processor import WorkflowCoordinator
from processors.blog_content_processor import BlogContentProcessor
from config import COLLECTION_REQUEST_DELAY


class CollectionProcessor(WorkflowCoordinator):
    """合集处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.blog_processor = BlogContentProcessor(client, debug)
    
    def make_valid_filename(self, filename: str) -> str:
        """创建有效的文件名"""
        try:
            # 步骤 1: 移除或替换所有非 ASCII 字符，以避免在 Windows GBK 环境下进行字符串操作时出现隐式编码错误
            # 使用 'ignore' 忽略无法编码的字符，确保字符串是 ASCII 安全的
            ascii_safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
            
            # 步骤 2: 处理文件系统不允许的字符
            safe_filename = re.sub(r'[\\/*?:"<>|]', '_', ascii_safe_filename)
            
            # 步骤 3: 移除或替换可能导致编码问题的字符 (保留原有的 UTF-8 忽略逻辑，以防万一)
            safe_filename = safe_filename.encode('utf-8', 'ignore').decode('utf-8')
            return safe_filename
        except Exception as e:
            # 确保日志中的文件名是安全的，使用 repr()
            safe_filename_repr = repr(filename)
            self.logger.warning(f"文件名处理失败: {safe_filename_repr}, 使用默认名称: {e}")
            return "Unknown_Collection"
    
    def get_collection_metadata(self, collection_id: str) -> Dict[str, Any]:
        """获取合集元数据"""
        try:
            collection_meta = self.client.get_collection_list(collection_id, offset=0, limit=1)
            
            if not collection_meta or 'collection' not in collection_meta:
                self.logger.error(f"无法获取合集 '{collection_id}' 的元数据")
                return {}
            
            collection_info = collection_meta['collection']
            collection_name_raw = collection_info.get('name', 'Unknown Collection')
            self.logger.debug(f"合集信息: Name={repr(collection_name_raw)}, PostCount={collection_info.get('postCount')}")
            
            # 确保传递给 make_valid_filename 的是字符串类型
            safe_name_input = str(collection_name_raw)
            
            return {
                'id': collection_info.get('id', collection_id),
                'name': self.make_valid_filename(safe_name_input),
                'post_count': collection_info.get('postCount', 0),
                'description': collection_info.get('description', ''),
                'tags': collection_info.get('tags', ''),
                'blog_id': collection_info.get('blogId', '')
            }
        except Exception as e:
            # 记录一个通用的错误，避免在 handle_error 中打印包含特殊字符的异常字符串 e
            self.logger.error(f"获取合集元数据 {collection_id} 失败，可能存在编码问题。原始错误类型: {type(e).__name__}")
            # 原始的 handle_error 调用可能会再次触发编码问题，因此我们只记录一个安全的消息
            # self.handle_error(e, f"获取合集元数据 {collection_id}")
            return {}
    
    def fetch_collection_posts(self, collection_id: str, post_count: int) -> List[Dict[str, Any]]:
        """获取合集中的所有帖子"""
        try:
            limit_once = 50
            all_post_items = []
            
            for i in range(0, post_count, limit_once):
                self.logger.info(f"获取帖子 {i+1}-{min(i+limit_once, post_count)}...")
                
                response = self.client.get_collection_list(collection_id, offset=i, limit=limit_once)
                if response and 'items' in response:
                    all_post_items.extend(response['items'])
                
                # 添加延迟避免请求过于频繁
                import time
                time.sleep(COLLECTION_REQUEST_DELAY)
            
            self.logger.debug(f"成功获取 {len(all_post_items)} 个帖子项。")
            return all_post_items
        except Exception as e:
            self.handle_error(e, f"获取合集帖子 {collection_id}")
            return []
    
    def adapt_post_meta_for_processing(self, post_item: Dict[str, Any]) -> Dict[str, Any]:
        """将合集API的帖子结构适配为process_post期望的结构"""
        try:
            self.logger.debug(f"开始适配帖子元数据: {post_item.keys()}")
            post_data = post_item.get("post", {})
            blog_info = post_item.get("blogInfo", {})
            
            # 确保优先使用帖子对象中的blogId（如果可用）
            if 'blogId' in post_data and 'blogInfo' in post_data:
                 blog_info = post_data['blogInfo']
            
            adapted_post_meta = {
                "blogInfo": blog_info,
                "postData": {
                    "postView": post_data
                }
            }
            self.logger.debug(f"适配完成，postView ID: {post_data.get('id', 'N/A')}")
            
            return adapted_post_meta
        except Exception as e:
            self.handle_error(e, "适配帖子元数据")
            return {}
    
    def process_single_collection_post(self, post_item: Dict[str, Any], collection_name: str,
                                     index: int, download_comments: bool = False,
                                     download_images: bool = True) -> Dict[str, Any]:
        """处理合集中的单个帖子"""
        try:
            post_id = post_item.get("post", {}).get("id", "N/A")
            self.logger.debug(f"开始处理单个合集帖子 ID: {post_id}")
            
            # 适配帖子结构
            post_meta = self.adapt_post_meta_for_processing(post_item)
            if not post_meta:
                post_id = post_item.get("post", {}).get("id", "N/A")
                self.logger.error(f"适配帖子元数据失败，帖子ID: {post_id}。原始键: {post_item.keys()}")
                return {}
            
            # 添加帖子索引作为文件名前缀
            name_prefix = str(index + 1)
            
            # 使用博客内容处理器处理帖子
            result = self.blog_processor.process_single_post(
                post_meta=post_meta,
                name=collection_name,
                download_comments=download_comments,
                source_type="collection-collection",
                name_prefix=name_prefix,
                download_images=download_images
            )
            
            if not result:
                post_id = post_item.get("post", {}).get("id", "N/A")
                self.logger.error(f"博客内容处理器处理失败，帖子ID: {post_id}")
            else:
                post_id = post_item.get("post", {}).get("id", "N/A")
                self.logger.debug(f"帖子处理成功，帖子ID: {post_id}")
            
            return result
            
        except Exception as e:
            post_id = post_item.get("post", {}).get("id", "N/A")
            self.handle_error(e, f"处理合集帖子 {post_id}")
            return {}
    
    def process(self, collection_id: str, download_comments: bool = False, 
                download_images: bool = True) -> Dict[str, Any]:
        """处理合集的主要接口"""
        try:
            self.logger.info(f"开始处理合集 '{collection_id}'...")
            
            # 获取合集元数据
            collection_metadata = self.get_collection_metadata(collection_id)
            if not collection_metadata:
                return {}
            
            collection_name = collection_metadata['name']
            post_count = collection_metadata['post_count']
            
            self.logger.info(f"合集: '{collection_name}', 帖子数量: {post_count}")
            
            if post_count == 0:
                self.logger.info("合集中没有帖子")
                return {"success": True, "message": "合集中没有帖子"}
            
            # 获取所有帖子
            all_post_items = self.fetch_collection_posts(collection_id, post_count)
            
            if not all_post_items:
                self.logger.error("没有找到合集中的帖子")
                return {"success": False, "message": "没有找到合集中的帖子"}
            
            # 处理所有帖子
            processed_posts = []
            failed_posts = []
            
            def process_post_item(post_item, index):
                result = self.process_single_collection_post(
                    post_item, collection_name, index, download_comments, download_images
                )
                return result, post_item.get("post", {}).get("id", "Unknown") if not result else None
            
            # 使用工作流协调器处理进度
            results = self.process_with_progress_with_results(
                all_post_items, 
                process_post_item, 
                f"Collection '{collection_name}'"
            )
            
            # 处理结果
            for result, failed_id in results:
                if result:
                    processed_posts.append(result)
                elif failed_id:
                    failed_posts.append(failed_id)
            
            # 返回处理结果
            result = {
                "success": True,
                "collection_name": collection_name,
                "total_posts": len(all_post_items),
                "processed_posts": len(processed_posts),
                "failed_posts": len(failed_posts),
                "failed_post_ids": failed_posts
            }
            
            self.logger.info(f"合集 '{collection_name}' 处理完成: {len(processed_posts)}/{len(all_post_items)} 成功")
            
            return result
            
        except Exception as e:
            self.handle_error(e, f"处理合集 {collection_id}")
            return {"success": False, "error": str(e)}