"""
博客内容处理器
专门处理博客帖子的内容提取、格式化和保存
"""
import json
import os
from typing import Dict, Any, List, Optional
from processors.base_processor import ContentProcessor, OutputFormatter
from utils.path_manager import path_manager
from config import POST_DETAIL_REQUEST_DELAY


class GiftContentHandler:
    """付费彩蛋内容处理器"""
    
    @staticmethod
    def resolve_article(json_info: Optional[Dict[str, Any]]) -> Optional[str]:
        """解析文章内容，包括付费彩蛋内容"""
        try:
            if isinstance(json_info, dict):
                content = json_info['response']['posts'][0]['post']['content'].strip()
                return_content_data = json_info['response']['posts'][0]['post'].get('returnContent', [None])[0]
                
                if return_content_data:
                    return_content = return_content_data.get('content', None)
                    if return_content:
                        gift_content_html = (
                            '<h3>以下为彩蛋内容</h3>\n'
                            '<p id="GiftContent" style="white-space: pre-line;">'
                            f'{return_content}</p>'
                        )
                        return content + '\n' + gift_content_html
                return content
            else:
                return None

        except KeyError as e:
            print(f"解析JSON时发生错误: {e}")
            return None

    @staticmethod
    def resolve_picture(content: Optional[Dict[str, Any]]) -> str:
        """解析图片内容，包括付费彩蛋图片"""
        if content is None:
            raise ValueError("内容为空，无法解析图片URL")
        
        try:
            # 解析普通图片链接
            url_all: List = list(json.loads(content['response']['posts'][0]['post']['photoLinks']))
            
            # 获取付费彩蛋图片链接
            return_content = content['response']['posts'][0]['post'].get('returnContent', None)
            
            if return_content:
                return_img_all = return_content[0].get('images', [])
                for img in return_img_all:
                    url_all.append(img)
            
            # 确保JSON格式正确
            return str(url_all).replace("'", '"').replace('True', 'true').replace('False', 'false')
        
        except KeyError:
            raise ValueError("无法解析图片URL，缺少必要的字段")

    @staticmethod
    def has_gift_content(content: Optional[Dict[str, Any]]) -> bool:
        """检查帖子是否包含付费彩蛋内容"""
        if content is None:
            return False
        
        try:
            show_gift = content['response']['posts'][0]['post'].get('showGift', False)
            return_content = content['response']['posts'][0]['post'].get('returnContent', [])
            
            return bool(show_gift) and bool(return_content)
        except KeyError:
            return False


class BlogContentProcessor(ContentProcessor):
    """博客内容处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
        self.output_formatter = OutputFormatter()
        self.gift_handler = GiftContentHandler()
    
    def extract_photo_links(self, post_detail_json: Dict[str, Any]) -> List[str]:
        """从帖子数据中提取图片链接，包括付费彩蛋图片"""
        try:
            # 普通图片链接
            photo_links_str = post_detail_json["response"]["posts"][0]["post"].get("photoLinks", "[]")
            photos = json.loads(photo_links_str)
            photo_links = [p.get("raw") or p.get("orign") for p in photos if isinstance(p, dict)]
            
            # 检查是否有付费彩蛋图片
            if self.gift_handler.has_gift_content(post_detail_json):
                # 使用resolve_picture函数获取包含所有图片的列表
                all_photo_links_str = self.gift_handler.resolve_picture(post_detail_json)
                all_photo_links = json.loads(all_photo_links_str)
                return all_photo_links
            else:
                return photo_links
        except (json.JSONDecodeError, KeyError) as e:
            self.handle_error(e, "提取图片链接")
            return []
    
    def extract_post_content(self, post_detail_json: Dict[str, Any]) -> str:
        """提取帖子内容"""
        try:
            post = post_detail_json["response"]["posts"][0]["post"]
            
            if post.get("type") == 1:  # 文本帖子
                # 使用resolve_article函数处理包含付费彩蛋的文章内容
                resolved_content = self.gift_handler.resolve_article(post_detail_json)
                content = self.output_formatter.convert_html_to_text(
                    resolved_content or post.get("content", "")
                )
            elif post.get("type") == 2:  # 图片帖子
                content = "[Photo Post]"
            else:
                content = "[Unknown Post Type]"
            
            return content
        except Exception as e:
            self.handle_error(e, "提取帖子内容")
            return ""
    
    def get_post_metadata(self, post_detail_json: Dict[str, Any]) -> Dict[str, str]:
        """获取帖子元数据"""
        try:
            return self.output_formatter.format_post_metadata(
                post_detail_json["response"]["posts"][0]
            )
        except Exception as e:
            self.handle_error(e, "获取帖子元数据")
            return {}
    
    def format_post_as_text(self, post_detail_json: Dict[str, Any], 
                           photo_paths: List[str] = [], 
                           comments_text: str = "") -> str:
        """将帖子格式化为文本"""
        try:
            metadata = self.get_post_metadata(post_detail_json)
            content = self.extract_post_content(post_detail_json)
            
            # 构建文本内容
            text_parts = [
                f"标题: {metadata.get('title', 'Untitled')}",
                f"发布时间: {metadata.get('publish_time', '')}",
                f"作者: {metadata.get('author', 'Unknown Author')}",
                f"作者LOFTERID: {metadata.get('blog_id', 'Unknown ID')}",
                f"Tags: {metadata.get('tags', '')}",
                f"Link: {metadata.get('blog_url', '')}",
                "",
                "[正文]",
                content,
                "\n\n\n\n",
                "【评论】"
            ]
            
            if comments_text:
                text_parts.append(comments_text)
            else:
                text_parts.append("(暂无评论)")
            
            # 如果有图片，添加图片信息
            if photo_paths:
                text_parts.insert(-2, "\n[下载的图片]\n" + "\n".join(photo_paths))
            
            return "\n".join(text_parts)
        except Exception as e:
            self.handle_error(e, "格式化帖子文本")
            return ""
    
    def save_post_data(self, post_detail_json: Dict[str, Any], 
                      mode: str, name: str, base_filename: str,
                      download_comments: bool = False,
                      download_images: bool = True) -> Dict[str, Any]:
        """保存帖子数据，返回文件路径信息"""
        import time
        
        # 添加请求延迟
        time.sleep(POST_DETAIL_REQUEST_DELAY)
        
        result = {
            "json_file": "",
            "text_file": "",
            "photo_files": [],
            "comments_file": ""
        }
        
        try:
            # 保存JSON数据
            json_dir = path_manager.get_json_dir(mode, name, "blog")
            json_file = os.path.join(json_dir, f"{base_filename}.json")
            self.save_json_data(post_detail_json, json_file)
            result["json_file"] = json_file
            
            # 处理图片
            photo_paths = []
            post = post_detail_json["response"]["posts"][0]["post"]
            if post.get("type") == 2 and download_images:  # 图片帖子
                photo_links = self.extract_photo_links(post_detail_json)
                if photo_links:
                    from processors.base_processor import MediaProcessor
                    media_processor = MediaProcessor(self.client, self.debug)
                    photo_dir = path_manager.get_photo_dir(mode, name)
                    photo_paths = media_processor.download_images(
                        photo_links, photo_dir, base_filename
                    )
            result["photo_files"] = photo_paths
            
            # 处理评论
            comments_text = ""
            if download_comments:
                comment_processor = self.get_comment_processor()
                if comment_processor:
                    post_id = post.get('id')
                    blog_id = post.get('blogInfo', {}).get('blogId')
                    if post_id and blog_id:
                        comments_text = comment_processor.process_post_comments(
                            post_id, blog_id, mode, name
                        )
                        
                        # 保存评论到单独文件
                        comments_dir = path_manager.get_json_dir(mode, name, "comments")
                        comments_file = os.path.join(comments_dir, f"{base_filename}_comments.txt")
                        self.save_text_data(comments_text, comments_file)
                        result["comments_file"] = comments_file
            
            # 保存文本文件
            text_dir = path_manager.get_output_dir(mode, name)
            text_file = os.path.join(text_dir, f"{base_filename}.txt")
            text_content = self.format_post_as_text(post_detail_json, photo_paths, comments_text)
            self.save_text_data(text_content, text_file)
            result["text_file"] = text_file
            
            self.logger.info(f"帖子数据保存完成: {base_filename}")
            
        except Exception as e:
            self.handle_error(e, f"保存帖子数据 {base_filename}")
        
        return result
    
    def get_comment_processor(self):
        """获取评论处理器"""
        from processors.comment_processor import CommentProcessor
        return CommentProcessor(self.client, self.debug)
    
    def process_single_post(self, post_meta: Dict[str, Any],
                           name: str, download_comments: bool = False,
                           source_type: str = "blog",
                           name_prefix: str = "",
                           download_images: bool = True) -> Dict[str, Any]:
        """处理单个帖子"""
        try:
            # 获取帖子详情
            post_detail_json = self.client.fetch_post_detail(post_meta)
            if not post_detail_json or "response" not in post_detail_json or not post_detail_json["response"].get("posts"):
                post_id = post_meta.get('postData', {}).get('postView', {}).get('id', 'Unknown')
                self.logger.error(f"无法获取帖子详情: {post_id}")
                self.logger.debug(f"post_meta内容: {post_meta}")
                return {}
            
            # 获取帖子信息用于生成文件名
            post = post_detail_json["response"]["posts"][0]["post"]
            title = post.get("title", "Untitled")
            author = post["blogInfo"].get("blogNickName", "Unknown Author")
            
            # 生成基础文件名
            base_filename = self.output_formatter.format_post_filename(title, author, name_prefix)
            
            # 转换source_type到模式名称
            mode_mapping = {
                "tag-tag": "tag",
                "collection-collection": "collection",
                "blog": "blog",
                "subscription": "blog"
            }
            mode = mode_mapping.get(source_type, source_type.split("-")[0] if "-" in source_type else source_type)
            
            # 保存帖子数据
            result = self.save_post_data(
                post_detail_json, mode, name, base_filename,
                download_comments, download_images
            )
            
            if not result:
                self.logger.error(f"保存帖子数据失败: {base_filename}")
            
            return result
            
        except Exception as e:
            post_id = post_meta.get('postData', {}).get('postView', {}).get('id', 'Unknown')
            self.handle_error(e, f"处理单个帖子 {post_id}")
            return {}
