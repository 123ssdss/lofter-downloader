"""
评论处理模块 - 完整版本
包含评论获取、格式化、保存的所有功能

Author: Refactored from 6 files into 1 (because bruh, 6 files was too much)
"""
import os
import json
import time
import re
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from network import LofterClient
from config import (
    COMMENT_REQUEST_DELAY, 
    L2_COMMENT_REQUEST_DELAY, 
    COMMENT_MAX_WORKERS,
    GROUP_COMMENTS_BY_QUOTE
)
from utils.path_manager import path_manager


# ============================================================================
# 评论获取器 - CommentFetcher
# ============================================================================

class CommentFetcher:
    """评论获取器，负责从Lofter API获取评论数据"""
    
    def __init__(self, client: LofterClient):
        self.client = client
        self.L1_COMMENTS_URL = "https://api.lofter.com/comment/l1/page.json"
        self.L2_COMMENTS_URL = "https://api.lofter.com/comment/l2/page/abtest.json"
    
    def fetch_all_comments(self, post_id: str, blog_id: str, max_retries: int = 3) -> Dict:
        """获取帖子的所有评论（包括L1和L2）"""
        for attempt in range(max_retries):
            try:
                self.client._log(f"获取帖子 {post_id} 的评论 (尝试 {attempt + 1}/{max_retries})")
                
                all_l1_comments = self._fetch_all_l1_comments(post_id, blog_id)
                
                if not all_l1_comments:
                    return {"hot_list": [], "all_list": []}
                
                hot_comments = [c for c in all_l1_comments if c.get("is_hot_comment", False)]
                
                hot_comments_with_replies = self._fetch_replies_for_comments(
                    post_id, blog_id, hot_comments
                )
                all_comments_with_replies = self._fetch_replies_for_comments(
                    post_id, blog_id, all_l1_comments
                )
                
                return {
                    "hot_list": hot_comments_with_replies,
                    "all_list": all_comments_with_replies
                }
                
            except Exception as e:
                self.client._log(f"获取评论时出错 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    self.client._log(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    self.client._log(f"所有重试都失败了，返回空结果")
                    return {"hot_list": [], "all_list": []}
    
    def _fetch_all_l1_comments(self, post_id: str, blog_id: str) -> List[Dict]:
        """获取所有L1评论（分页处理）"""
        all_comments = []
        offset = 0
        page = 1
        
        while True:
            params = {
                "postId": post_id,
                "blogId": blog_id,
                "offset": offset,
                "product": "lofter-android-8.2.18",
                "needGift": 0,
                "openFansVipPlan": 0,
                "dunType": 1
            }
            
            response = self.client._make_request("GET", self.L1_COMMENTS_URL, params=params)
            
            if not response or response.get("code") != 0 or "data" not in response:
                self.client._log(f"第{page}页L1评论获取失败")
                break
            
            normal_comments = response["data"].get("list", [])
            hot_comments = response["data"].get("hotList", [])
            
            unique_page_comments = self._deduplicate_comments(
                normal_comments, hot_comments, all_comments
            )
            
            if not unique_page_comments:
                self.client._log(f"第{page}页没有新评论，停止获取")
                break
            
            all_comments.extend(unique_page_comments)
            self.client._log(
                f"第{page}页: {len(normal_comments)}条普通 + {len(hot_comments)}条热门 = "
                f"{len(unique_page_comments)}条唯一评论"
            )
            
            next_offset = response["data"].get("offset", -1)
            if next_offset == -1:
                self.client._log("没有更多页面了 (offset = -1)")
                break
            
            offset = next_offset
            page += 1
            time.sleep(COMMENT_REQUEST_DELAY)
        
        self.client._log(f"共收集了 {len(all_comments)} 条L1评论，来自 {page-1} 页")
        return all_comments
    
    def _deduplicate_comments(
        self, 
        normal_comments: List[Dict], 
        hot_comments: List[Dict],
        existing_comments: List[Dict]
    ) -> List[Dict]:
        """评论去重"""
        existing_ids = {c.get("id") for c in existing_comments}
        unique_comments = []
        seen_ids = set()
        
        for comment in hot_comments:
            comment_id = comment.get("id")
            if comment_id and comment_id not in existing_ids and comment_id not in seen_ids:
                comment["is_hot_comment"] = True
                unique_comments.append(comment)
                seen_ids.add(comment_id)
        
        for comment in normal_comments:
            comment_id = comment.get("id")
            if comment_id and comment_id not in existing_ids and comment_id not in seen_ids:
                comment["is_hot_comment"] = False
                unique_comments.append(comment)
                seen_ids.add(comment_id)
        
        return unique_comments
    
    def _fetch_replies_for_comments(
        self, 
        post_id: str, 
        blog_id: str, 
        comments: List[Dict]
    ) -> List[Dict]:
        """为评论列表获取所有L2回复（并发处理）"""
        comments_with_replies = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:
            future_to_comment = {
                executor.submit(
                    self._fetch_replies_for_single_comment, 
                    post_id, blog_id, comment
                ): comment
                for comment in comments if "id" in comment
            }
            
            for future in concurrent.futures.as_completed(future_to_comment):
                try:
                    result = future.result()
                    if result:
                        comments_with_replies.append(result)
                except Exception as e:
                    self.client._log(f"处理评论时出错: {e}")
        
        return comments_with_replies
    
    def _fetch_replies_for_single_comment(
        self, 
        post_id: str, 
        blog_id: str, 
        l1_comment: Dict
    ) -> Dict:
        """为单个L1评论获取L2回复"""
        comment_id = l1_comment["id"]
        
        normalized_comment = self._normalize_comment(l1_comment, "L1")
        
        embedded_replies = l1_comment.get("l2Comments", [])
        expected_reply_count = l1_comment.get("l2Count", 0)
        
        normalized_replies = [
            self._normalize_comment(reply, "L2") 
            for reply in embedded_replies
        ]
        
        if expected_reply_count > len(embedded_replies):
            additional_replies = self._fetch_l2_comments(post_id, blog_id, comment_id)
            
            embedded_ids = {r.get("id") for r in embedded_replies}
            for reply in additional_replies:
                if reply.get("id") not in embedded_ids:
                    normalized_replies.append(self._normalize_comment(reply, "L2"))
            
            total_found = len(normalized_replies)
            if total_found < expected_reply_count:
                self.client._log(
                    f"警告: 评论 {comment_id} 期望 {expected_reply_count} 条回复，"
                    f"实际找到 {total_found} 条"
                )
        
        normalized_comment["replies"] = normalized_replies
        normalized_comment["l2_count"] = len(normalized_replies)
        
        return normalized_comment
    
    def _fetch_l2_comments(
        self, 
        post_id: str, 
        blog_id: str, 
        comment_id: str, 
        max_retries: int = 2
    ) -> List[Dict]:
        """获取L2评论（带重试机制）"""
        for attempt in range(max_retries):
            time.sleep(L2_COMMENT_REQUEST_DELAY)
            
            params = {
                "postId": post_id,
                "blogId": blog_id,
                "id": comment_id,
                "offset": 0,
                "fromSrc": "",
                "fromId": ""
            }
            
            response = self.client._make_request("GET", self.L2_COMMENTS_URL, params=params)
            
            if not response or not isinstance(response, dict):
                self.client._log(f"L2评论响应无效，评论ID: {comment_id}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    self.client._log(f"{wait_time}秒后重试L2评论 {comment_id}")
                    time.sleep(wait_time)
                    continue
                return []
            
            if response.get("code") != 0:
                error_code = response.get("code", "unknown")
                error_msg = response.get("msg", "unknown error")
                self.client._log(
                    f"L2 API错误，评论ID {comment_id}: 错误码 {error_code}, 消息: {error_msg}"
                )
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                return []
            
            l2_comments = self._extract_l2_comments_from_response(response)
            if l2_comments:
                self.client._log(f"成功获取评论 {comment_id} 的 {len(l2_comments)} 条L2回复")
                return l2_comments
            
            self.client._log(f"评论 {comment_id} 的响应中没有找到L2评论")
            return []
        
        return []
    
    def _extract_l2_comments_from_response(self, response: Dict) -> List[Dict]:
        """从响应中提取L2评论列表"""
        if "data" in response and "list" in response["data"]:
            return response["data"]["list"]
        elif "list" in response:
            return response["list"]
        elif "data" in response and isinstance(response["data"], list):
            return response["data"]
        return []
    
    def _normalize_comment(self, raw_comment: Dict, comment_type: str = "L1") -> Dict:
        """标准化评论格式"""
        publisher_info = raw_comment.get('publisherBlogInfo', {})
        author = {
            "blogNickName": publisher_info.get('blogNickName', ''),
            "blogId": publisher_info.get('blogId', ''),
            "blogName": publisher_info.get('blogName', ''),
            "avatar": publisher_info.get('smallLogo', '')
        }
        
        publish_time = raw_comment.get('publishTime', 0)
        publish_time_formatted = ''
        if publish_time:
            publish_time_formatted = datetime.fromtimestamp(
                publish_time / 1000
            ).strftime('%Y-%m-%d %H:%M:%S')
        
        normalized = {
            "id": raw_comment.get('id', ''),
            "content": raw_comment.get('content', '').strip(),
            "publishTime": publish_time,
            "publishTimeFormatted": publish_time_formatted,
            "likeCount": raw_comment.get('likeCount', 0),
            "ipLocation": raw_comment.get('ipLocation', ''),
            "quote": raw_comment.get('quote', ''),
            "author": author,
            "type": comment_type,
            "replies": [],
            "l2_count": 0,
            "replyTo": raw_comment.get('replyTo', {})
        }
        
        emotes = raw_comment.get('emotes', [])
        if emotes:
            normalized['emotes'] = emotes
        
        return normalized


# ============================================================================
# 评论格式化器 - CommentFormatter
# ============================================================================

class CommentFormatter:
    """评论格式化器，负责将评论数据格式化为文本输出"""
    
    def format_comments(self, structured_comments: Dict) -> str:
        """格式化评论为文本"""
        if not structured_comments:
            return ""
        
        result = "[热门评论]\n"
        result += self._format_comment_list(structured_comments.get("hot_list", []))
        result += "\n[全部评论]\n"
        result += self._format_comment_list(structured_comments.get("all_list", []))
        
        return result
    
    def _format_comment_list(self, comments: List[Dict]) -> str:
        """格式化评论列表"""
        if GROUP_COMMENTS_BY_QUOTE:
            return self._format_comments_grouped_by_quote(comments)
        else:
            return self._format_comments_in_order(comments)
    
    def _format_comments_grouped_by_quote(self, comments: List[Dict]) -> str:
        """按引用内容分组格式化评论"""
        grouped, non_quoted = self._group_comments_by_quote(comments)
        result = ""
        
        for quote, comments_list in grouped.items():
            result += f"----------({quote})----------\n"
            for idx, comment in enumerate(comments_list, 1):
                result += f"---------- (L0-{idx})\n"
                result += self._format_single_comment(comment, indent_level=0)
                result += self._format_replies(comment.get("replies", []), indent_level=1)
                result += "\n"
        
        for idx, comment in enumerate(non_quoted, 1):
            result += f"---------- (L0-{idx})\n"
            result += self._format_single_comment(comment, indent_level=0)
            result += self._format_replies(comment.get("replies", []), indent_level=1)
            result += "\n"
        
        return result
    
    def _format_comments_in_order(self, comments: List[Dict]) -> str:
        """按原始顺序格式化评论"""
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
        """格式化单个评论"""
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
        """格式化回复列表"""
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
        """按引用内容分组评论"""
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


# ============================================================================
# 评论保存器 - CommentSaver
# ============================================================================

class CommentSaver:
    """评论保存器，负责将评论数据保存到文件系统"""
    
    def __init__(self, client: LofterClient):
        self.client = client
    
    def save_comments(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str = 'comment', 
        name: str = ''
    ):
        """保存评论到文件系统"""
        self._save_as_json(post_id, blog_id, structured_comments, mode, name)
        self._save_user_format(post_id, blog_id, structured_comments, mode, name)
    
    def _save_as_json(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str, 
        name: str
    ):
        """保存为JSON格式"""
        try:
            json_dir = self._get_json_dir(mode, name)
            filename = f"comments_{post_id}_{blog_id}.json"
            filepath = os.path.join(json_dir, filename)
            
            os.makedirs(json_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(structured_comments, f, ensure_ascii=False, indent=2)
            
            self.client._log(f"JSON评论已保存: {filepath}")
            
        except Exception as e:
            self.client._log(f"保存JSON评论时出错: {e}")
    
    def _save_user_format(
        self, 
        post_id: str, 
        blog_id: str, 
        structured_comments: Dict, 
        mode: str, 
        name: str
    ):
        """保存为用户格式（简化的文本格式）"""
        try:
            json_dir = self._get_json_dir(mode, name)
            filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            filepath = os.path.join(json_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                all_comments = structured_comments.get("all_list", [])
                
                for comment in all_comments:
                    comment_id = comment.get("id", "unknown")
                    content = comment.get("content", "")
                    f.write(f"[l1 {comment_id}]\n")
                    f.write(f"{content}\n")
                    
                    replies = comment.get("replies", [])
                    for reply in replies:
                        reply_id = reply.get("id", "unknown")
                        reply_content = reply.get("content", "")
                        f.write(f"   [l2 {reply_id}]\n")
                        f.write(f"    {reply_content}\n")
                    
                    f.write("\n")
            
            self.client._log(f"用户格式评论已保存: {filepath}")
            
        except Exception as e:
            self.client._log(f"保存用户格式评论时出错: {e}")
    
    def _get_json_dir(self, mode: str, name: str) -> str:
        """根据模式获取JSON目录"""
        mode_dir_map = {
            'blog': lambda: path_manager.get_json_dir('blog', name or '', 'comments'),
            'tag': lambda: path_manager.get_json_dir('tag', name or 'default_tag_name', 'comments'),
            'collection': lambda: path_manager.get_json_dir('collection', name or 'default_collection_name', 'comments'),
            'comment': lambda: path_manager.get_json_dir('comment', name or '', 'comments'),
            'subscription': lambda: path_manager.get_json_dir('subscription', name or '', 'comments'),
            'update': lambda: path_manager.get_json_dir('update', name or '', 'comments')
        }
        
        return mode_dir_map.get(mode, mode_dir_map['comment'])()


# ============================================================================
# 评论模式处理器 - CommentModeProcessor
# ============================================================================

class CommentModeProcessor:
    """评论模式处理器，处理单个帖子的评论"""
    
    def __init__(self, client: LofterClient):
        self.client = client
    
    def process(self, post_url_or_id: str, blog_id: str = None):
        """处理评论模式"""
        print(f"开始处理评论模式，帖子: {post_url_or_id}")
        
        post_id, blog_id = self._parse_post_info(post_url_or_id, blog_id)
        
        if not post_id:
            print("无法提取到有效的post_id")
            return
        
        if not blog_id:
            print("需要提供blog_id")
            return
        
        post_detail = self.client.fetch_post_detail_by_id(post_id, blog_id)
        
        if not self._is_valid_post_detail(post_detail):
            print(f"无法获取帖子详情: {post_id}")
            return
        
        post = post_detail["response"]["posts"][0]["post"]
        base_filename = self._create_safe_filename(post)
        
        self._save_post_json(post_detail, base_filename)
        
        comments_text = process_comments(self.client, post_id, blog_id, mode='comment')
        self._save_comments_text(comments_text, base_filename)
        
        self._save_post_content(post, base_filename, comments_text)
        
        print(f"评论模式处理完成: {base_filename}")
    
    def _parse_post_info(self, post_url_or_id: str, blog_id: str = None) -> tuple:
        """解析帖子信息"""
        if post_url_or_id.startswith('http'):
            post_id = self._extract_post_id_from_url(post_url_or_id)
            if not blog_id:
                blog_id = self._extract_blog_id_from_url(post_url_or_id)
        else:
            post_id = post_url_or_id
        
        return post_id, blog_id
    
    def _extract_post_id_from_url(self, url: str) -> str:
        """从URL中提取帖子ID"""
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
        """从URL中提取博客ID"""
        pattern = r'//(.*?)\.lofter\.com'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def _is_valid_post_detail(self, post_detail: dict) -> bool:
        """检查帖子详情是否有效"""
        return (
            post_detail and 
            "response" in post_detail and 
            post_detail["response"].get("posts")
        )
    
    def _create_safe_filename(self, post: dict) -> str:
        """创建安全的文件名"""
        title = post.get("title", "Untitled")
        author = post["blogInfo"].get("blogNickName", "Unknown Author")
        
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
        safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
        
        return f"({safe_title} by {safe_author})"
    
    def _save_post_json(self, post_detail: dict, base_filename: str):
        """保存帖子JSON数据"""
        json_dir = path_manager.get_json_dir('comment', 'posts', 'blog')
        json_file_path = os.path.join(json_dir, f"{base_filename}.json")
        
        os.makedirs(json_dir, exist_ok=True)
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(post_detail, f, ensure_ascii=False, indent=4)
    
    def _save_comments_text(self, comments_text: str, base_filename: str):
        """保存评论文本"""
        comments_dir = path_manager.get_json_dir('comment', 'posts', 'comments')
        comments_file_path = os.path.join(comments_dir, f"{base_filename}_comments.txt")
        
        os.makedirs(comments_dir, exist_ok=True)
        with open(comments_file_path, 'w', encoding='utf-8') as f:
            f.write(comments_text)
    
    def _save_post_content(self, post: dict, base_filename: str, comments_text: str):
        """保存帖子内容（包含评论）"""
        import html
        
        output_dir = path_manager.get_output_dir('comment', 'posts')
        output_file_path = os.path.join(output_dir, f"{base_filename}.txt")
        
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
            html_content = post.get("content", "")
            if html_content:
                text = html.unescape(html_content)
                text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
                text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
                text = re.sub(r'<[^>]+>', '', text)
                content = text.strip()
        elif post.get("type") == 2:
            content = "[Photo Post with potential images]"
        
        # 写入文件
        with open(output_file_path, 'w', encoding='utf-8') as f:
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


# ============================================================================
# 公共接口函数
# ============================================================================

def process_comments(
    client: LofterClient, 
    post_id: str, 
    blog_id: str, 
    mode: str = 'comment', 
    name: str = ''
) -> str:
    """
    处理评论的主函数（整合接口）
    
    Args:
        client: LofterClient实例
        post_id: 帖子ID
        blog_id: 博客ID
        mode: 模式 ('tag', 'collection', 'blog', 'comment', 'subscription')
        name: 名称（标签名、收藏集名等）
        
    Returns:
        格式化后的评论文本
    """
    fetcher = CommentFetcher(client)
    formatter = CommentFormatter()
    saver = CommentSaver(client)
    
    structured_comments = fetcher.fetch_all_comments(post_id, blog_id)
    
    if not structured_comments or not structured_comments.get("all_list"):
        return ""
    
    saver.save_comments(post_id, blog_id, structured_comments, mode, name)
    
    formatted_text = formatter.format_comments(structured_comments)
    
    return formatted_text


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
