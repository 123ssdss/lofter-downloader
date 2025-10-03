import json
import time
import sys
from datetime import datetime
import re
from urllib.parse import urlparse
import requests
from requests.cookies import create_cookie
import concurrent.futures
from config import REQUEST_TIMEOUT, TEXT_MAX_WORKERS, REQUEST_DELAY, BETWEEN_PAGES_DELAY, COMMENT_REQUEST_DELAY, COMMENT_MAX_WORKERS

# 默认User-Agent和产品信息，固定在此文件中
DEFAULT_USER_AGENT = "LOFTER-Android 7.6.12 (V2272A; Android 13; null) WIFI"
LOFTER_PRODUCT = "lofter-android-7.6.12"

# --- Constants ---
API_BASE_URL = "https://api.lofter.com"
TAG_POSTS_URL = f"{API_BASE_URL}/newapi/tagPosts.json"
POST_DETAIL_URL = f"{API_BASE_URL}/oldapi/post/detail.api"
L1_COMMENTS_URL = f"{API_BASE_URL}/comment/l1/page.json"
L2_COMMENTS_URL = f"{API_BASE_URL}/comment/l2/page/abtest.json"
COLLECTION_URL = f"{API_BASE_URL}/v1.1/postCollection.api"
SUBSCRIPTION_URL = f"{API_BASE_URL}/newapi/subscribeCollection/list.json"

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
    def __init__(self, cookies=None, headers=None, debug=False):
       self.session = requests.Session()
       self.debug = debug
       self.auth_key = None
       self.ntes_sess = None
       self.authorization = None
       self.lofter_sess = None
       
       self.session.headers.update({
           "User-Agent": DEFAULT_USER_AGENT,
           "Accept-Encoding": "br,gzip",
           "Connection": "Keep-Alive",
           "lofProduct": LOFTER_PRODUCT,
       })
       if headers:
           self.session.headers.update(headers)

       if cookies:
           self.auth_key = cookies.get("LOFTER-PHONE-LOGIN-AUTH")
           self.ntes_sess = cookies.get("NTES_SESS")
           self.authorization = cookies.get("Authorization")
           self.lofter_sess = cookies.get("LOFTER_SESS")
           # Set cookies on the session for general requests
           for name, value in cookies.items():
               cookie = create_cookie(domain=".lofter.com", name=name, value=value)
               self.session.cookies.set_cookie(cookie)

    def _log(self, message):
        if self.debug:
            print(f"[DEBUG] {datetime.now().strftime('%H:%M:%S')} - {message}")

    def _make_request(self, method, url, params=None, data=None, headers=None, max_retries=3):
       """Makes an HTTP request with retry logic."""
       self._log(f"Request: {method} {url}")
       if params: self._log(f"Params: {params}")
       if data: self._log(f"Data: {data}")

       request_headers = self.session.headers.copy()
       if headers:
           request_headers.update(headers)
       
       # Critical fix: The collection API endpoint is sensitive to User-Agent.
       # Removing all User-Agent related headers to force requests library's default,
       # which mimics the behavior of the original working script.
       for key in ('User-Agent', 'lofProduct'):
           if key in request_headers:
               del request_headers[key]

       # Log the cookies that will be sent with the request
       cookies_to_send = dict(self.session.cookies)
       self._log(f"Request Headers: {request_headers}")
       self._log(f"Request Cookies: {cookies_to_send}")

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
               return json_response
           except (requests.RequestException, json.JSONDecodeError) as e:
               self._log(f"Request to {url} failed (attempt {attempt + 1}/{max_retries}): {e}")
               if 'response' in locals() and hasattr(response, 'text'):
                   self._log(f"Response text on error: {response.text[:500]}...")
               time.sleep(2 ** attempt)
       return None

    def fetch_posts_by_tag(self, tag, list_type="total", timelimit="", blog_type=""):
        """Fetches all post metadata for a given tag."""
        all_posts = []
        permalinks = set()
        offset = 0
        
        sys.stdout.write(f"Fetching posts for tag: {tag}\r")
        sys.stdout.flush()

        while True:
            data = {
                "product": "lofter-android-8.1.28",
                "postTypes": blog_type,
                "offset": str(offset),
                "postYm": timelimit,
                "tag": tag,
                "type": list_type
            }
            
            response = self._make_request("POST", TAG_POSTS_URL, data=data)

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
            sys.stdout.write(f"Tag '{tag}': Fetched {len(all_posts)} posts...\r")
            sys.stdout.flush()
            time.sleep(BETWEEN_PAGES_DELAY)
        
        sys.stdout.write("\033[K")
        print(f"Tag '{tag}': Fetching complete. Found {len(all_posts)} unique posts.")
        return all_posts
        
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
        response = self._make_request("GET", L2_COMMENTS_URL, params=params)
        return response

    def fetch_all_comments_for_post(self, post_id, blog_id, return_structure=False):
        """Fetches all comments for a post, including replies, using improved method based on deepseek implementation."""
        self._log(f"Fetching comments for post {post_id}")
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
            
            # Combine normal comments and hot comments
            normal_comments = response["data"].get("list", [])
            hot_comments = response["data"].get("hotList", [])
            page_comments = normal_comments + hot_comments
            
            # If this page has no comments, we've retrieved all data
            if not page_comments:
                self._log(f"No comments found on page {page}, stopping")
                break
            
            # Add to all comments
            all_comments.extend(page_comments)
            
            # Log comment counts
            self._log(f"Page {page}: {len(normal_comments)} normal + {len(hot_comments)} hot = {len(page_comments)} comments")
            
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
        
        if not all_comments:
            return "" if not return_structure else []
        
        # If return_structure is True, return structured data instead of formatted text
        if return_structure:
            # First, fetch all L2 comments and map them to their L1 comments
            comments_with_replies = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:  # Reduced workers to avoid rate limiting
                future_to_comment = {
                    executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                    for c in all_comments if "id" in c
                }
                
                for future in concurrent.futures.as_completed(future_to_comment):
                    try:
                        result = future.result()
                        if result:  # Only add if we have a result
                            comments_with_replies.append(result)
                    except Exception as e:
                        self._log(f"Error processing comment: {str(e)}")
            
            return comments_with_replies
        else:
            # Original behavior - return formatted text
            comments_text = ""
            with concurrent.futures.ThreadPoolExecutor(max_workers=COMMENT_MAX_WORKERS) as executor:  # Reduced workers to avoid rate limiting
                future_to_comment = {
                    executor.submit(self._process_l1_comment_with_replies, post_id, blog_id, c): c
                    for c in all_comments if "id" in c
                }
                
                for future in concurrent.futures.as_completed(future_to_comment):
                    try:
                        result = future.result()
                        if result:  # Only add text if we have a result
                            comments_text += self._format_comment_with_replies_text(result)
                    except Exception as e:
                        self._log(f"Error processing comment: {str(e)}")
            
            return comments_text

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
        result = f"\n--- Comment by {normalized_comment['author']['blogNickName']} ---\n"
        result += f"Content: {normalized_comment['content']}\n"
        result += f"Time: {normalized_comment['publishTimeFormatted']}\n"
        result += f"Likes: {normalized_comment['likeCount']}\n"
        
        if normalized_comment['replies']:
            result += "  --- Replies ---\n"
            for reply in normalized_comment['replies']:
                result += f"    Reply by {reply['author']['blogNickName']}\n"
                result += f"    Content: {reply['content']}\n"
                result += f"    Time: {reply['publishTimeFormatted']}\n"
                result += f"    Likes: {reply['likeCount']}\n"
        
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
           headers = {
               "user-agent": "Dart/3.6 (dart:io)",
               "accept-encoding": "gzip",
               "host": parsed_url.netloc
           }
           # Log photo download request in debug mode
           cookies_to_send = dict(self.session.cookies)
           self._log(f"Photo download request: GET {url}")
           self._log(f"Photo download headers: {headers}")
           self._log(f"Photo download cookies: {cookies_to_send}")
           response = self.session.get(url, headers=headers, stream=True, timeout=20)
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
       headers = {
           'Accept-Encoding': "br,gzip",
           'content-type': "application/x-www-form-urlencoded; charset=utf-8",
       }
       
       try:
           # Log the cookies that will be sent with the request (from session)
           cookies_to_send = dict(self.session.cookies)
           self._log(f"Request (Bypassing Session): POST {COLLECTION_URL}")
           self._log(f"Params: {params}")
           self._log(f"Data: {payload}")
           self._log(f"Headers: {headers}")
           self._log(f"Session Cookies: {cookies_to_send}")
           
           response = requests.post(COLLECTION_URL, params=params, data=payload, headers=headers, timeout=15)
           
           self._log(f"Response Status: {response.status_code}")
           self._log(f"Response Body: {response.text[:500]}...")  # Limit body output to prevent too much text
           response.raise_for_status()
           response_json = response.json()
           
           if response_json and "response" in response_json:
               return response_json['response']
       except (requests.RequestException, json.JSONDecodeError) as e:
           self._log(f"Request failed: {e}")
           if 'response' in locals() and hasattr(response, 'text'):
               self._log(f"Response text on error: {response.text[:500]}...")

       return None

    def fetch_subscription_collections(self, limit=50):
       """Fetches all subscription collections from user's subscriptions."""
       all_collections = []
       offset = 0
       total_expected = float('inf')  # Will update from response
       
       while len(all_collections) < total_expected:
           headers = {}
           cookie_parts = []
           if self.auth_key:
               headers['lofter-phone-login-auth'] = self.auth_key
               cookie_parts.append(f"LOFTER-PHONE-LOGIN-AUTH={self.auth_key}")
           if self.ntes_sess:
               cookie_parts.append(f"NTES_SESS={self.ntes_sess}")
           if self.authorization:
               headers['Authorization'] = self.authorization
               cookie_parts.append(f"Authorization={self.authorization}")
           if self.lofter_sess:
               cookie_parts.append(f"LOFTER_SESS={self.lofter_sess}")
           if cookie_parts:
               headers['Cookie'] = "; ".join(cookie_parts)

           # Log the headers and cookies being used for subscription request
           if self.debug:
               self._log(f"Subscription request headers: {headers}")
               self._log(f"Subscription request cookies: {'; '.join(cookie_parts) if cookie_parts else 'None'}")

           params = { 'offset': offset, 'limit': limit }
           response = self._make_request("GET", SUBSCRIPTION_URL, params=params, headers=headers)
           
           response_data = response.get("data") if response else None
           if not response_data:
               break
               
           # Update total expected count and offset
           if 'subscribeCollectionCount' in response_data:
               total_expected = response_data['subscribeCollectionCount']
           
           if 'offset' in response_data:
               offset = response_data['offset']
           
           # Extract collections from response
           collections = response_data.get("collections", [])
           all_collections.extend(collections)

           # Break if no more collections returned or we've reached the expected total
           if not collections or len(collections) < limit or len(all_collections) >= total_expected:
               break
           
       return all_collections

    def fetch_subscription_posts(self, limit=50):
       """Fetches all post metadata from user's subscriptions."""
       # For now, we'll return the collection data as posts so the main flow works
       # This is for backward compatibility with the existing main.py code
       collections = self.fetch_subscription_collections(limit)
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