import json
import time
import sys
from datetime import datetime
import re
from urllib.parse import urlparse
import requests
import concurrent.futures
from config import REQUEST_TIMEOUT, TEXT_MAX_WORKERS, REQUEST_DELAY, BETWEEN_PAGES_DELAY, COMMENT_REQUEST_DELAY, L2_COMMENT_REQUEST_DELAY, COMMENT_MAX_WORKERS
from config import USER_COOKIE  # Import user-provided cookie from config
from utils.logger import BeautifulLogger, ProgressDisplay



# --- Constants ---
API_BASE_URL = "https://api.lofter.com"
TAG_POSTS_URL = f"{API_BASE_URL}/newapi/tagPosts.json"
POST_DETAIL_URL = f"{API_BASE_URL}/oldapi/post/detail.api"
L1_COMMENTS_URL = f"{API_BASE_URL}/comment/l1/page.json"
L2_COMMENTS_URL = f"{API_BASE_URL}/comment/l2/page/abtest.json"
COLLECTION_URL = f"{API_BASE_URL}/v1.1/postCollection.api"
SUBSCRIPTION_URL = f"{API_BASE_URL}/newapi/subscribeCollection/list.json"

# Define fixed headers to be used in all network methods
FIXED_HEADERS = {
    "user-agent": "LOFTER-Android 8.0.12 (LM-V409N; Android 15; null) WIFI",
    "market": "LGE",
    "androidid": "3451efd56bgg6h47",
    "accept-encoding": "gzip",
    "x-device": "qv+Dz73SObtbEFG7P0Gq12HkjzNb+iOK6KHWTPKHBTEZu26C6MJOMukkAG7dETo2",
    "x-reqid": "0H62K0V7",
    "content-type": "application/x-www-form-urlencoded",
    "dadeviceid": "2ef9ea6c17b7c6881c71915a4fefd932edc01af0",
    "lofproduct": "lofter-android-8.0.12",
    "host": "api.lofter.com",
    "portrait": "eyJpbWVpIjoiMzQ1MWVmZDU2YmdnNmg0NyIsImFuZHJvaWRJZCI6IjM0NTFlZmQ1NmJnZzZoNDciLCJvYWlkIjoiMzJiNGQyYzM0ODY1MDg0MiIsIm1hYyI6IjAyOjAwOjAwOjAwOjAwOjAwIiwicGhvbmUiOiIxNTkzNDg2NzI5MyJ9",
    "Cookie": f"{USER_COOKIE['name']}={USER_COOKIE['value']}"
}

def _format_comment(comment, indent_level=0):
    """Formats a single comment dictionary into a readable string."""
    indent = "  " * indent_level
    author = comment.get("publisherBlogInfo", {}).get("blogNickName", "Unknown")
    publish_time = datetime.fromtimestamp(comment.get("publishTime", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
    content = comment.get('content', '').strip()
    
    return (
        f"{indent}Author: {author} ({publish_time})\n"
        f"{indent}Content: {content}\n"
    )

class LofterClient:
    """
    A client for interacting with the Lofter API.
    """
    def __init__(self, headers=None, debug=False):
       self.session = requests.Session()
       self.debug = debug
       self.logger = BeautifulLogger.create_debug_logger("LofterClient")

       self.session.headers.update(FIXED_HEADERS)
       if headers:
           self.session.headers.update(headers)

    def _log(self, message):
        if self.debug:
            # 确保消息在打印时不会因为编码问题而失败
            safe_message = str(message).encode('utf-8', 'replace').decode('utf-8')
            self.logger.debug(safe_message)
    def _make_request(self, method, url, params=None, data=None, headers=None, max_retries=3):
        """Makes an HTTP request with retry logic."""
        self._log(f"Request: {method} {url}")
        if params: self._log(f"Params: {params}")
        if data: self._log(f"Data: {data}")

        # Use fixed headers for all requests
        request_headers = FIXED_HEADERS.copy()
        if headers:
            request_headers.update(headers)

        try:
            self._log(f"Request Headers: {request_headers}")

            for attempt in range(max_retries):
                try:
                    if method.upper() == "GET":
                        response = self.session.get(url, params=params, headers=request_headers, timeout=REQUEST_TIMEOUT)
                    else:
                        response = self.session.post(url, data=data, headers=request_headers, timeout=REQUEST_TIMEOUT)

                    self._log(f"Response Status: {response.status_code}")
                    self._log(f"Response Body: {response.text[:500]}...")  # Limit body output to prevent too much text
                    response.raise_for_status()
                    json_response = response.json()
                    self._log("Successfully decoded JSON response.")
                    
                    # Check for API error in response content
                    if isinstance(json_response, dict) and json_response.get("code") == 500:
                        error_msg = json_response.get("msg", "Unknown error")
                        self._log(f"API error: {error_msg} (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            wait_time = 3 + 2 ** attempt  # 3, 5, 9 seconds
                            self._log(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self._log(f"All retry attempts failed for request to {url}")
                            return None
                    
                    return json_response
                except (requests.RequestException, json.JSONDecodeError) as e:
                    self._log(f"Request to {url} failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if 'response' in locals() and hasattr(response, 'text'):
                        self._log(f"Response text on error: {response.text[:500]}...")
                    if attempt < max_retries - 1:
                        wait_time = 3 + 2 ** attempt  # 3, 5, 9 seconds
                        self._log(f"Retrying network error in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return None
        except Exception as e:
            self._log(f"Unhandled exception during request: {e}")
        return None

    def fetch_posts_by_tag(self, tag, list_type=None, timelimit=None, blog_type=None):
        """Fetches all post metadata for a given tag."""
        # Import default values from config
        from config import DEFAULT_LIST_TYPE, DEFAULT_TIME_LIMIT, DEFAULT_BLOG_TYPE
        
        # Use default values from config if parameters are not provided
        if list_type is None:
            list_type = DEFAULT_LIST_TYPE
        if timelimit is None:
            timelimit = DEFAULT_TIME_LIMIT
        if blog_type is None:
            blog_type = DEFAULT_BLOG_TYPE
            
        all_posts = []
        all_responses = []  # 保存所有响应
        permalinks = set()
        offset = 0
        
        # 使用纯文字显示替代进度条，INFO显示为绿色
        print(f"\033[32m[INFO]\033[0m LofterClient 开始获取标签 '{tag}' 的帖子内容...")

        while True:
            data = {
                "postTypes": blog_type,
                "offset": str(offset),
                "postYm": timelimit,
                "tag": tag,
                "type": list_type,
                "limit": 10  # Fetch 10 posts at a time
            }

            # Use fixed headers for the request
            response = self._make_request("POST", TAG_POSTS_URL, data=data)
            
            # 保存完整的响应
            if response:
                all_responses.append(response)

            if not response or "data" not in response or not response["data"].get("list"):
                self._log(f"No more posts found for tag '{tag}' or API error.")
                break

            posts = response["data"]["list"]
            
            if not posts:
                break

            first_post_permalink = posts[0]["postData"]["postView"]["permalink"]
            if first_post_permalink in permalinks:
                break
            
            new_posts = [p for p in posts if p["postData"]["postView"]["permalink"] not in permalinks]
            self._log(f"Found {len(new_posts)} new posts in this batch.")
            all_posts.extend(new_posts)
            for post in new_posts:
                permalinks.add(post["postData"]["postView"]["permalink"])

            offset = response["data"]["offset"]
            print(f"\033[32m[INFO]\033[0m LofterClient 获取标签 '{tag}': {len(all_posts)} 个帖子")
            time.sleep(BETWEEN_PAGES_DELAY)
        
        print(f"\033[32m[INFO]\033[0m LofterClient 标签 '{tag}' 获取完成: {len(all_posts)} 个独特帖子")
        
        # 保存完整的响应到JSON文件
        self._save_tag_responses(tag, all_responses)
        
        return all_posts
    
    def _save_tag_responses(self, tag, responses):
        """保存标签的完整响应到JSON文件"""
        try:
            import os
            import json
            from utils.path_manager import path_manager
            
            # 获取保存路径 - 直接在tag目录下，不使用comments子目录
            json_dir = os.path.join(path_manager.base_json_dir, 'tag', tag)
            os.makedirs(json_dir, exist_ok=True)
            filepath = os.path.join(json_dir, 'tagresponse.json')
            
            # 保存响应
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(responses, f, ensure_ascii=False, indent=2)
                
            self._log(f"Saved tag responses to {filepath}")
        except Exception as e:
            self._log(f"Error saving tag responses: {str(e)}")
        
    def fetch_post_detail(self, post_meta):
        blog_info = post_meta["blogInfo"]
        post_view = post_meta["postData"]["postView"]
        self._log(f"Fetching post detail ID {post_view['id']} from blog {blog_info['blogName']}")
        
        data = {
            "targetblogid": blog_info["blogId"],
            "blogdomain": f"{blog_info['blogName']}.lofter.com",
            "postid": str(post_view["id"]),
            "product": "lofter-android-7.9.7.2"
        }
        
        return self._make_request("POST", POST_DETAIL_URL, data=data)
    
    
    def fetch_post_detail_by_id(self, post_id, blog_id):
        """根据post_id和blog_id直接获取帖子详情."""
        self._log(f"Fetching post detail by ID {post_id} from blog {blog_id}")
        
        # 尝试获取博客域名
        blog_info_response = self._make_request("GET", f"{API_BASE_URL}/v1.1/bloginfo.api", params={
            "product": "lofter-android-7.9.7.2",
            "blogids": str(blog_id)
        })
        
        blog_domain = f"{blog_id}.lofter.com"
        if (blog_info_response and
            "response" in blog_info_response and
            "blogs" in blog_info_response["response"] and
            len(blog_info_response["response"]["blogs"]) > 0):
            blog_name = blog_info_response["response"]["blogs"][0].get("blogname")
            if blog_name:
                blog_domain = f"{blog_name}.lofter.com"
        
        data = {
            "targetblogid": str(blog_id),
            "blogdomain": blog_domain,
            "postid": str(post_id),
            "product": "lofter-android-7.9.7.2"
        }
        
        return self._make_request("POST", POST_DETAIL_URL, data=data)


    def _fetch_l2_comments(self, post_id, blog_id, comment_id, max_retries=2):
        """Fetches L2 comments (replies) for an L1 comment with retry logic."""
        for attempt in range(max_retries):
            result = self._fetch_l2_comments_single(post_id, blog_id, comment_id)
            
            # Check if we need to retry based on error
            if (isinstance(result, dict) and
                result.get("code") == 500 and
                attempt < max_retries - 1):
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2, 4 seconds
                self._log(f"Retrying L2 request for comment {comment_id} in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
                
            return result
        
        return result

    def _fetch_l2_comments_single(self, post_id, blog_id, comment_id):
        """Single attempt to fetch L2 comments (replies) for an L1 comment."""
        params = {"postId": post_id, "blogId": blog_id, "id": comment_id, "offset": 0, "fromSrc": "", "fromId": ""}
        # 在请求之前添加延迟
        time.sleep(L2_COMMENT_REQUEST_DELAY)
        response = self._make_request("GET", L2_COMMENTS_URL, params=params)
        return response

    def fetch_all_comments_for_post(self, post_id, blog_id, return_structure=False, max_retries=3, mode='comment', name=''):
        """Fetches all comments for a post, including replies, using improved method based on deepseek implementation."""
        for attempt in range(max_retries):
            try:
                self._log(f"Fetching comments for post {post_id} (attempt {attempt + 1}/{max_retries})")
                offset = 0
                all_comments = []
                page = 1
                
                # Fetch L1 comments using pagination until no more data
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
                    
                    response = self._make_request("GET", L1_COMMENTS_URL, params=params)

                    if not response or response.get("code") != 0 or "data" not in response:
                        self._log(f"Failed to fetch L1 comments for post {post_id} (page {page})")
                        break

                    # Check if we have the expected structure
                    if "data" not in response:
                        self._log("Unexpected L1 comments structure")
                        break
                    
                    # Separate hot comments and normal comments to avoid duplicates
                    normal_comments = response["data"].get("list", [])
                    hot_comments = response["data"].get("hotList", [])
                    
                    # Create a set of comment IDs to avoid duplicates when combining
                    comment_ids = set()
                    unique_page_comments = []
                    
                    # Add hot comments first (they are typically more important)
                    for comment in hot_comments:
                        comment_id = comment.get("id")
                        if comment_id and comment_id not in comment_ids:
                            comment["is_hot_comment"] = True  # Mark as hot comment
                            unique_page_comments.append(comment)
                            comment_ids.add(comment_id)
                    
                    # Add normal comments that aren't already in the list
                    for comment in normal_comments:
                        comment_id = comment.get("id")
                        if comment_id and comment_id not in comment_ids:
                            comment["is_hot_comment"] = False  # Mark as normal comment
                            unique_page_comments.append(comment)
                            comment_ids.add(comment_id)
                    
                    # If this page has no unique comments, we've retrieved all data
                    if not unique_page_comments:
                        self._log(f"No unique comments found on page {page}, stopping")
                        break
                    
                    # Add unique comments to all comments
                    all_comments.extend(unique_page_comments)
                    
                    # Log comment counts
                    self._log(f"Page {page}: {len(normal_comments)} normal + {len(hot_comments)} hot = {len(unique_page_comments)} unique comments")
                    
                    # Check if there are more pages
                    next_offset = response["data"].get("offset", -1)
                    if next_offset == -1:
                        self._log("No more pages available (offset = -1)")
                        break
                        
                    offset = next_offset
                    self._log(f"Moving to next page with offset: {offset}")
                    
                    # Increment page counter
                    page += 1
                    
                    # Add a small delay between pages to avoid rate limiting
                    time.sleep(COMMENT_REQUEST_DELAY)
                
                self._log(f"Total L1 comments collected: {len(all_comments)} from {page-1} pages")
                
                # Create structured data with separate hot and normal comments
                structured_comments = {
                    "hot_list": [comment for comment in all_comments if comment.get("is_hot_comment", False)],
                    "all_list": all_comments
                }
                
                if not all_comments:
                    return "" if not return_structure else []
                
                # If return_structure is True, return structured data instead of formatted text
                if return_structure:
                    # Process hot comments
                    hot_comments_with_replies = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:
                        future_to_comment = {
                            executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                            for c in structured_comments["hot_list"] if "id" in c
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_comment):
                            try:
                                result = future.result()
                                if result:  # Only add if we have a result
                                    hot_comments_with_replies.append(result)
                            except Exception as e:
                                self._log(f"Error processing hot comment: {str(e)}")
                    
                    # Process all comments
                    all_comments_with_replies = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:
                        future_to_comment = {
                            executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                            for c in structured_comments["all_list"] if "id" in c
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_comment):
                            try:
                                result = future.result()
                                if result:  # Only add if we have a result
                                    all_comments_with_replies.append(result)
                            except Exception as e:
                                self._log(f"Error processing all comment: {str(e)}")
                    
                    # Create final structured result
                    structured_result = {
                        "hot_list": hot_comments_with_replies,
                        "all_list": all_comments_with_replies
                    }
                    
                    # Save original HTTP JSON responses to JSON directory
                    self._save_original_responses(post_id, blog_id, structured_result, mode, name)
                    
                    return structured_result
                else:
                    # Format hot comments first
                    hot_comments_text = "[热门评论]\n"
                    with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:
                        future_to_comment = {
                            executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                            for c in structured_comments["hot_list"] if "id" in c
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_comment):
                            try:
                                result = future.result()
                                if result:  # Only add if we have a result
                                    hot_comments_text += self._format_comment_with_replies_text(result)
                            except Exception as e:
                                self._log(f"Error processing hot comment: {str(e)}")
                                
                    # Format all comments next
                    all_comments_text = "[全部评论]\n"
                    with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:
                        future_to_comment = {
                            executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                            for c in structured_comments["all_list"] if "id" in c
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_comment):
                            try:
                                result = future.result()
                                if result:  # Only add if we have a result
                                    all_comments_text += self._format_comment_with_replies_text(result)
                            except Exception as e:
                                self._log(f"Error processing all comment: {str(e)}")
                    
                    # Combine both texts
                    comments_text = hot_comments_text + "\n" + all_comments_text
                    
                    return comments_text
                    
            except Exception as e:
                self._log(f"Error fetching comments for post {post_id} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2, 4, 6 seconds
                    self._log(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self._log(f"All retry attempts failed for post {post_id}. Returning empty result.")
                    return "" if not return_structure else []
                    
    def _save_original_responses(self, post_id, blog_id, structured_result, mode='comment', name=''):
        """保存原始的HTTP JSON响应到JSON目录，根据模式选择路径"""
        import os
        from utils.path_manager import path_manager
        
        try:
            # 根据不同模式选择不同的目录结构
            if mode == 'blog':
                # json/blog/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
            elif mode == 'tag':
                # json/tag/tag名字/comments
                json_dir = path_manager.get_json_dir(mode, name or 'default_tag_name', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
            elif mode == 'collection':
                # json/collection/collection名字/comments
                json_dir = path_manager.get_json_dir(mode, name or 'default_collection_name', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
            elif mode == 'comment':
                # json/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
            elif mode == 'update':
                # json/update/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
            else:
                # 默认情况
                json_dir = path_manager.get_json_dir('comment', name or '', 'comments')
                filename = f"comments_{post_id}_{blog_id}.json"
                
            filepath = os.path.join(json_dir, filename)
            
            # 保存完整的结构化结果
            os.makedirs(json_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(structured_result, f, ensure_ascii=False, indent=2)
                
            self._log(f"Saved original comment responses to {filepath}")
            
            # 同时保存为用户要求的格式
            self._save_comments_in_user_format(post_id, blog_id, structured_result, mode, name)
        except Exception as e:
            self._log(f"Error saving original responses: {str(e)}")
            
    def _save_comments_in_user_format(self, post_id, blog_id, structured_result, mode='comment', name=''):
        """按照用户要求的格式保存评论，根据模式选择路径"""
        import os
        from utils.path_manager import path_manager
        
        try:
            # 根据不同模式选择不同的目录结构
            if mode == 'blog':
                # json/blog/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            elif mode == 'tag':
                # json/tag/tag名字/comments
                json_dir = path_manager.get_json_dir(mode, name or 'default_tag_name', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            elif mode == 'collection':
                # json/collection/collection名字/comments
                json_dir = path_manager.get_json_dir(mode, name or 'default_collection_name', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            elif mode == 'comment':
                # json/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            elif mode == 'update':
                # json/update/comments
                json_dir = path_manager.get_json_dir(mode, name or '', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
            else:
                # 默认情况
                json_dir = path_manager.get_json_dir('comment', name or '', 'comments')
                filename = f"comments_formatted_{post_id}_{blog_id}.txt"
                
            filepath = os.path.join(json_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                # 遍历所有评论（包含热门评论和普通评论）
                all_comments = structured_result.get("all_list", [])
                
                for comment in all_comments:
                    # 写入主评论信息
                    f.write(f"发布人：{comment.get('author', {}).get('blogNickName', 'Unknown')}\n")
                    f.write(f"时间：{comment.get('publishTimeFormatted', '')}\n")
                    f.write(f"内容：{comment.get('content', '').strip()}\n")
                    f.write(f"点赞数：{comment.get('likeCount', 0)}\n")
                    
                    # 添加IP位置信息（如果有）
                    ip_location = comment.get('ipLocation', '')
                    if ip_location:
                        f.write(f"IP属地：{ip_location}\n")
                    
                    # 添加引用内容（如果有）
                    quote = comment.get('quote', '')
                    if quote:
                        f.write(f"引用：{quote}\n")
                    
                    # 添加表情信息（如果有）
                    emotes = comment.get('emotes', [])
                    if emotes:
                        f.write("表情：\n")
                        for emote in emotes:
                            f.write(f"  - {emote['name']} ({emote['url']})\n")
                    
                    # 处理回复
                    replies = comment.get("replies", [])
                    if replies:
                        f.write("\n---回复列表---\n")
                        for idx, reply in enumerate(replies, 1):
                            f.write(f"回复{idx}：\n")
                            f.write(f"  作者：{reply.get('author', {}).get('blogNickName', 'Unknown')}\n")
                            f.write(f"  时间：{reply.get('publishTimeFormatted', '')}\n")
                            f.write(f"  内容：{reply.get('content', '').strip()}\n")
                            f.write(f"  点赞数：{reply.get('likeCount', 0)}\n")
                            
                            # 添加IP位置信息（如果有）
                            reply_ip_location = reply.get('ipLocation', '')
                            if reply_ip_location:
                                f.write(f"  IP属地：{reply_ip_location}\n")
                            
                            # 添加表情信息（如果有）
                            reply_emotes = reply.get('emotes', [])
                            if reply_emotes:
                                f.write("  表情：\n")
                                for emote in reply_emotes:
                                    f.write(f"    - {emote['name']} ({emote['url']})\n")
                    
                    f.write("\n")
                
            self._log(f"Saved comments in user format to {filepath}")
        except Exception as e:
            self._log(f"Error saving comments in user format: {str(e)}")

    def _process_l1_comment_with_replies(self, post_id, blog_id, l1_comment):
        """Process a single L1 comment and get its L2 replies."""
        comment_id = l1_comment["id"]
        
        # Create normalized comment format for this L1 comment
        normalized_comment = self._normalize_comment_format(l1_comment, "L1")
        
        # Check if there are embedded L2 comments in the L1 response
        embedded_l2_comments = l1_comment.get("l2Comments", [])
        l2_count = l1_comment.get("l2Count", 0)
        
        # Process embedded L2 comments first
        normalized_replies = [self._normalize_comment_format(reply, "L2") for reply in embedded_l2_comments]
        
        # If there are more expected L2 comments than embedded, fetch additional ones
        if l2_count > len(embedded_l2_comments):
            # Get L2 comments (replies) for this L1 comment with retry
            l2_data = self._fetch_l2_comments(post_id, blog_id, comment_id)
            
            # Check if the response is valid
            if l2_data is None:
                self._log(f"L2 response is None for comment {comment_id}")
            elif isinstance(l2_data, str):
                self._log(f"L2 response is string for comment {comment_id}: {l2_data[:100]}...")
            elif not isinstance(l2_data, dict):
                self._log(f"L2 response is not a dict for comment {comment_id}: {type(l2_data)}")
            elif l2_data.get("error"):
                # Handle error response
                status_code = l2_data.get("status_code", "unknown")
                message = l2_data.get("message", "unknown error")
                self._log(f"L2 request failed for comment {comment_id}: Status {status_code}, Message: {message}")
            elif l2_data.get("code") != 0:
                # Handle API error response (code 500)
                error_code = l2_data.get("code", "unknown")
                error_msg = l2_data.get("msg", "unknown error")
                self._log(f"L2 API error for comment {comment_id}: Code {error_code}, Message: {error_msg}")
            else:
                self._log(f"Successfully retrieved L2 comments for L1 comment {comment_id}")
                
                # Try different response structures
                # Try from data.list
                additional_l2_comments = []
                if "data" in l2_data and "list" in l2_data["data"]:
                    additional_l2_comments = l2_data["data"]["list"]
                # Try from root-level list
                elif "list" in l2_data:
                    additional_l2_comments = l2_data["list"]
                # Try from data directly
                elif "data" in l2_data and isinstance(l2_data["data"], list):
                    additional_l2_comments = l2_data["data"]
                
                if additional_l2_comments:
                    # Add unique additional L2 comments that aren't already in embedded replies
                    for l2_comment in additional_l2_comments:
                        # Skip comments already included in embedded replies
                        if any(emb.get("id") == l2_comment.get("id") for emb in embedded_l2_comments):
                            continue
                        normalized_replies.append(self._normalize_comment_format(l2_comment, "L2"))
                    
                    # Check if we found all expected replies
                    total_found = len(embedded_l2_comments) + len([r for r in normalized_replies if r not in [self._normalize_comment_format(emb, "L2") for emb in embedded_l2_comments]])
                    if total_found < l2_count:
                        self._log(f"Warning: Found {total_found} replies but expected {l2_count} for comment {comment_id}")
                else:
                    self._log(f"No additional L2 comments found in response for comment {comment_id}")
        
        # Add replies to the normalized comment
        normalized_comment["replies"] = normalized_replies
        normalized_comment["l2_count"] = len(normalized_replies)
        
        return normalized_comment

    def _format_comment_with_replies_text(self, normalized_comment):
        """Format a normalized comment with its replies as text."""
        result = f"\n发布人：{normalized_comment['author']['blogNickName']}\n"
        result += f"时间：{normalized_comment['publishTimeFormatted']}\n"
        result += f"内容：{normalized_comment['content']}\n"
        result += f"点赞数：{normalized_comment['likeCount']}\n"
        
        # 添加IP位置信息（如果有）
        if normalized_comment.get('ipLocation'):
            result += f"IP属地：{normalized_comment['ipLocation']}\n"
        
        # 添加引用内容（如果有）
        if normalized_comment.get('quote'):
            result += f"引用：{normalized_comment['quote']}\n"
        
        # 添加表情信息（如果有）
        if normalized_comment.get('emotes'):
            result += "表情：\n"
            for emote in normalized_comment['emotes']:
                result += f"  - {emote['name']} ({emote['url']})\n"
        
        # 添加回复部分（如果有）
        if normalized_comment['replies']:
            result += "\n---回复列表---\n"
            for idx, reply in enumerate(normalized_comment['replies'], 1):
                result += f"回复{idx}：\n"
                result += f"  作者：{reply['author']['blogNickName']}\n"
                result += f"  时间：{reply['publishTimeFormatted']}\n"
                result += f"  内容：{reply['content']}\n"
                result += f"  点赞数：{reply['likeCount']}\n"
                
                # 添加IP位置信息（如果有）
                if reply.get('ipLocation'):
                    result += f"  IP属地：{reply['ipLocation']}\n"
                
                # 添加表情信息（如果有）
                if reply.get('emotes'):
                    result += "  表情：\n"
                    for emote in reply['emotes']:
                        result += f"    - {emote['name']} ({emote['url']})\n"
                
                result += "\n"
        
        result += "\n"
        return result

    def _normalize_comment_format(self, raw_comment, comment_type="L1"):
        """Normalizes the comment format to match the JSON structure in the example."""
        # Convert publisherBlogInfo to author
        publisher_info = raw_comment.get('publisherBlogInfo', {})
        author = {
            "blogNickName": publisher_info.get('blogNickName', ''),
            "blogId": publisher_info.get('blogId', ''),
            "blogName": publisher_info.get('blogName', ''),
            "avatar": publisher_info.get('smallLogo', '')
        }

        # Handle timestamps - Lofter API returns timestamps in milliseconds
        publish_time = raw_comment.get('publishTime', 0)
        publish_time_formatted = ''
        if publish_time:
            # Convert from milliseconds to seconds
            publish_time_formatted = datetime.fromtimestamp(publish_time / 1000).strftime('%Y-%m-%d %H:%M:%S')

        # Normalize the comment structure
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

        # Add emotes if present
        emotes = raw_comment.get('emotes', [])
        if emotes:
            normalized['emotes'] = emotes

        return normalized

    def download_photo(self, url, filepath):
       """Downloads a single photo."""
       try:
           parsed_url = urlparse(url)
           headers = FIXED_HEADERS.copy()
           headers.update({
               "host": parsed_url.netloc
           })
           # Log photo download request in debug mode
           self._log(f"Photo download request: GET {url}")
           self._log(f"Photo download headers: {headers}")

           try:
               response = self.session.get(url, headers=headers, stream=True, timeout=20)
           except Exception as e:
               self._log(f"Error during photo download request: {e}")
               return None

           self._log(f"Photo download response status: {response.status_code}")
           if response.status_code == 200:
               with open(filepath, 'wb') as f:
                   for chunk in response.iter_content(8192):
                       f.write(chunk)
               return filepath
       except requests.RequestException as e:
           self._log(f"Failed to download photo {url}: {e}")
       return None

    def get_collection_list(self, collection_id, offset=0, limit=15):
       """
       Direct port of the get_collection_list function from the original script.
       Bypasses the session to send a clean request, exactly mimicking the original script.
       """
       params = {'product': "lofter-android-7.6.12"}
       payload = f"method=getCollectionDetail&offset={offset}&limit={limit}&collectionid={collection_id}&order=1"
       headers = FIXED_HEADERS.copy()

       try:
           # Log the request details
           self._log(f"Request (Bypassing Session): POST {COLLECTION_URL}")
           self._log(f"Params: {params}")
           self._log(f"Data: {payload}")
           self._log(f"Headers: {headers}")

           response = requests.post(COLLECTION_URL, params=params, data=payload, headers=headers, timeout=15)

           self._log(f"Response Status: {response.status_code}")
           self._log(f"Response Body: {response.text[:500]}...")  # Limit body output to prevent too much text
           response.raise_for_status()

           # 强制使用 UTF-8 解码响应内容，以避免 Windows GBK 编码问题
           # 使用 response.content 获取原始字节，并手动解码
           response_text = response.content.decode('utf-8', errors='replace')
           self._log(f"Decoded Response Text: {response_text[:500]}")

           response_json = json.loads(response_text)

           if response_json and "response" in response_json:
               return response_json['response']
       except (requests.RequestException, json.JSONDecodeError) as e:
           self._log(f"Request failed: {e}")
           if 'response' in locals() and hasattr(response, 'text'):
               self._log(f"Response text on error: {response.text[:500]}...")

       return None

    def fetch_subscription_collections(self):
       """Fetches all subscription collections from user's subscriptions until completion."""
       # 重新实现此方法以使用get_subs方法，确保只发送选中的cookie类型
       all_collections = []
       offset = 0
       limit_once = 50  # 每次请求获取的数量
       total_expected = float('inf')  # Will update from response
       
       # 使用get_subs方法，它会正确处理选中的cookie类型
       response = self.get_subs(offset, limit_once)
       if not response:
           return []
           
       data = response.get('data')
       if not data:
           return []
           
       # Update total expected count and offset
       if 'subscribeCollectionCount' in data:
           total_expected = data['subscribeCollectionCount']
       
       if 'offset' in data:
           offset = data['offset']
       
       # Extract collections from response
       collections = data.get("collections", [])
       all_collections.extend(collections)

       # 获取剩余的集合，直到获取完为止
       while len(all_collections) < total_expected:
           response = self.get_subs(len(all_collections), limit_once)
           if not response:
               break
           data = response.get('data')
           if not data:
               break
           collections = data.get("collections", [])
           if not collections:
               break  # 没有更多数据了
           all_collections.extend(collections)

       return all_collections

    def fetch_subscription_posts(self):
       """Fetches all post metadata from user's subscriptions."""
       # For now, we'll return the collection data as posts so the main flow works
       # This is for backward compatibility with the existing main.py code
       collections = self.fetch_subscription_collections()
       # Convert collections to a format that looks like posts for compatibility
       posts_format = []
       for collection in collections:
           # Create a post-like structure for each collection
           posts_format.append({
               "post": {
                   "id": collection.get("collectionId", ""),
                   "title": f"Collection: {collection.get('name', 'Unknown')}",
                   "type": "collection",
                   "collectionInfo": collection
               },
               "blogInfo": collection.get("blogInfo", {})
           })
       return posts_format

    def get_subs(self, offset=0, limit_once=50):
       """Fetches subscription list."""
       # Set request parameters
       params = {
           'offset': offset,
           'limit': limit_once
       }

       headers = FIXED_HEADERS.copy()

       # Make the request
       response = self._make_request("GET", SUBSCRIPTION_URL, params=params, headers=headers)

       if response and response.get('code') == 0:  # Successful response
           self._log("Successfully fetched subscription list")
           return response
       else:
           # Log error if response contains error information
           if response:
               error_msg = response.get('msg', 'Unknown error')
               error_code = response.get('code', 'Unknown')
               self._log(f"Subscription API error: {error_msg} (code: {error_code})")
           else:
               self._log("Failed to fetch subscription list: Request failed or no response")
           return None

    def save_subscription_list(self, auth_info, save_path='./results', sleep_time=0.1, limit_once=50):
       '''
       保存订阅列表到 txt 文件和 json 文件

       Args:
       auth_info: 登录信息字典，包含LOFTER-PHONE-LOGIN-AUTH和NTES_SESS
       save_path: 保存路径，默认为'./results'
       sleep_time: 请求间隔，默认为0.1秒
       limit_once: 次获取数量，默认为50
       '''
       # 为订阅模式使用专门的路径，实现隔离
       # 使用空字符串作为 name 参数，将直接创建在 output/subscription 下
       from utils.path_manager import path_manager
       output_dir = path_manager.get_output_dir('subscription', '')
       json_dir = path_manager.get_json_dir('subscription', 'subscription')

       import os
       os.makedirs(save_path, exist_ok=True)  # 确保 ./results 目录存在

       start = 0 # 起始位置
       response = self.get_subs(start)
       if not response:
           print("获取订阅列表失败")
           return
       data = response['data']
       offset = data['offset'] # 结束位置
       subscribeCollectionCount = data['subscribeCollectionCount']
       collections = data['collections']

       if subscribeCollectionCount > limit_once:
           for i in range(limit_once, subscribeCollectionCount, limit_once):
               time.sleep(sleep_time)
               response = self.get_subs(i, limit_once)
               if response:
                   data = response['data']
                   collections += data['collections']

       # 写入txt文件
       # 直接在 output 目录下创建 subscription.txt 文件
       txt_file_path = os.path.join('output', 'subscription.txt')
       os.makedirs('output', exist_ok=True)
       with open(txt_file_path, 'w', encoding='utf-8') as f:
           f.write(f"订阅总数: {subscribeCollectionCount}\n")
           f.write("="*50 + "\n")
           for c in collections:
               collection_id = c['collectionId']
               if not c.get('valid', True):  # 如果没有valid字段，默认为True
                   print(f'合集{collection_id}已失效')
                   continue
               collection_name = c['name']
               f.write(f'合集名：{collection_name}\n')
               f.write(f'合集ID：{collection_id}\n')

               # 只有当值存在且不为空时才写入
               author_name = c.get('blogInfo', {}).get('blogNickName', '')
               if author_name:
                   f.write(f'作者：{author_name}\n')
               collection_url = c.get('collectionUrl', '')
               if collection_url:
                   f.write(f'链接：{collection_url}\n')
               f.write("-" * 30 + "\n")
               print(f'合集名：{collection_name}，合集ID：{collection_id}')

       print(f'订阅信息保存至 {txt_file_path}')

       # 保存到用户要求的路径：./json/subscription.json
       user_json_path = os.path.join('json', 'subscription.json')
       os.makedirs('json', exist_ok=True)
       with open(user_json_path, 'w', encoding='utf-8') as f:
           json.dump(collections, f, ensure_ascii=False, indent=2)
       print(f'订阅信息JSON保存至 {user_json_path}')

    def fetch_html_content(self, url, timeout=30):
        """
        获取URL的HTML内容，支持cookies认证

        Args:
            url (str): 要访问的URL
            timeout (int): 超时时间（秒）

        Returns:
            str: HTML内容，如果失败则返回None
        """
        try:
            self._log(f"正在访问URL获取HTML内容: {url}")

            # 准备cookies
            cookies = {}
            if USER_COOKIE:
                cookies[USER_COOKIE["name"]] = USER_COOKIE["value"]

            # 准备浏览器headers（不要使用API的FIXED_HEADERS）
            browser_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # 使用独立的requests调用，避免session中的API headers干扰
            import requests
            response = requests.get(url, cookies=cookies, headers=browser_headers, timeout=timeout)
            
            if response.status_code == 200:
                self._log(f"成功获取HTML内容，长度: {len(response.text)}")
                return response.text
            else:
                self._log(f"访问URL失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            self._log(f"获取HTML内容时出错: {e}")
            return None