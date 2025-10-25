"""
评论获取模块
负责从API获取评论数据，包括L1和L2评论
"""
import time
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import COMMENT_REQUEST_DELAY, L2_COMMENT_REQUEST_DELAY, COMMENT_MAX_WORKERS


class CommentFetcher:
    """评论获取器，负责从Lofter API获取评论数据"""
    
    def __init__(self, client):
        """
        初始化评论获取器
        
        Args:
            client: LofterClient实例
        """
        self.client = client
        self.L1_COMMENTS_URL = "https://api.lofter.com/comment/l1/page.json"
        self.L2_COMMENTS_URL = "https://api.lofter.com/comment/l2/page/abtest.json"
    
    def fetch_all_comments(self, post_id: str, blog_id: str, max_retries: int = 3) -> Dict:
        """
        获取帖子的所有评论（包括L1和L2）
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            max_retries: 最大重试次数
            
        Returns:
            包含热门评论和全部评论的字典结构
        """
        for attempt in range(max_retries):
            try:
                self.client._log(f"获取帖子 {post_id} 的评论 (尝试 {attempt + 1}/{max_retries})")
                
                # 获取所有L1评论
                all_l1_comments = self._fetch_all_l1_comments(post_id, blog_id)
                
                if not all_l1_comments:
                    return {"hot_list": [], "all_list": []}
                
                # 分离热门评论和全部评论
                hot_comments = [c for c in all_l1_comments if c.get("is_hot_comment", False)]
                
                # 为所有评论获取L2回复
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
        """
        获取所有L1评论（分页处理）
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            
        Returns:
            L1评论列表
        """
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
            
            # 提取评论并去重
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
            
            # 检查是否还有下一页
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
        """
        评论去重
        
        Args:
            normal_comments: 普通评论列表
            hot_comments: 热门评论列表
            existing_comments: 已存在的评论列表
            
        Returns:
            去重后的评论列表
        """
        # 获取已存在的评论ID
        existing_ids = {c.get("id") for c in existing_comments}
        unique_comments = []
        seen_ids = set()
        
        # 先添加热门评论（标记为热门）
        for comment in hot_comments:
            comment_id = comment.get("id")
            if comment_id and comment_id not in existing_ids and comment_id not in seen_ids:
                comment["is_hot_comment"] = True
                unique_comments.append(comment)
                seen_ids.add(comment_id)
        
        # 再添加普通评论（不在热门中的）
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
        """
        为评论列表获取所有L2回复（并发处理）
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            comments: 评论列表
            
        Returns:
            包含回复的评论列表
        """
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
        """
        为单个L1评论获取L2回复
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            l1_comment: L1评论数据
            
        Returns:
            包含回复的标准化评论数据
        """
        comment_id = l1_comment["id"]
        
        # 标准化L1评论格式
        normalized_comment = self._normalize_comment(l1_comment, "L1")
        
        # 获取内嵌的L2评论
        embedded_replies = l1_comment.get("l2Comments", [])
        expected_reply_count = l1_comment.get("l2Count", 0)
        
        # 标准化内嵌的回复
        normalized_replies = [
            self._normalize_comment(reply, "L2") 
            for reply in embedded_replies
        ]
        
        # 如果期望的回复数量大于内嵌的数量，需要额外获取
        if expected_reply_count > len(embedded_replies):
            additional_replies = self._fetch_l2_comments(post_id, blog_id, comment_id)
            
            # 去重并添加额外的回复
            embedded_ids = {r.get("id") for r in embedded_replies}
            for reply in additional_replies:
                if reply.get("id") not in embedded_ids:
                    normalized_replies.append(self._normalize_comment(reply, "L2"))
            
            # 记录回复数量差异
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
        """
        获取L2评论（带重试机制）
        
        Args:
            post_id: 帖子ID
            blog_id: 博客ID
            comment_id: L1评论ID
            max_retries: 最大重试次数
            
        Returns:
            L2评论列表
        """
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
            
            # 检查响应
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
            
            # 提取L2评论列表
            l2_comments = self._extract_l2_comments_from_response(response)
            if l2_comments:
                self.client._log(f"成功获取评论 {comment_id} 的 {len(l2_comments)} 条L2回复")
                return l2_comments
            
            self.client._log(f"评论 {comment_id} 的响应中没有找到L2评论")
            return []
        
        return []
    
    def _extract_l2_comments_from_response(self, response: Dict) -> List[Dict]:
        """
        从响应中提取L2评论列表
        
        Args:
            response: API响应
            
        Returns:
            L2评论列表
        """
        # 尝试不同的响应结构
        if "data" in response and "list" in response["data"]:
            return response["data"]["list"]
        elif "list" in response:
            return response["list"]
        elif "data" in response and isinstance(response["data"], list):
            return response["data"]
        return []
    
    def _normalize_comment(self, raw_comment: Dict, comment_type: str = "L1") -> Dict:
        """
        标准化评论格式
        
        Args:
            raw_comment: 原始评论数据
            comment_type: 评论类型 ("L1" 或 "L2")
            
        Returns:
            标准化的评论字典
        """
        # 提取发布者信息
        publisher_info = raw_comment.get('publisherBlogInfo', {})
        author = {
            "blogNickName": publisher_info.get('blogNickName', ''),
            "blogId": publisher_info.get('blogId', ''),
            "blogName": publisher_info.get('blogName', ''),
            "avatar": publisher_info.get('smallLogo', '')
        }
        
        # 处理时间戳（毫秒转秒）
        publish_time = raw_comment.get('publishTime', 0)
        publish_time_formatted = ''
        if publish_time:
            publish_time_formatted = datetime.fromtimestamp(
                publish_time / 1000
            ).strftime('%Y-%m-%d %H:%M:%S')
        
        # 标准化评论结构
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
        
        # 添加表情（如果存在）
        emotes = raw_comment.get('emotes', [])
        if emotes:
            normalized['emotes'] = emotes
        
        return normalized
