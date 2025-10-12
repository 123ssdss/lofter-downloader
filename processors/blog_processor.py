import os
import json
import re
import html
import time
from datetime import datetime
from urllib.parse import urlparse
import concurrent.futures
from network import LofterClient
from utils.path_manager import path_manager
from utils.gift_content_handler import resolve_article, resolve_picture, has_gift_content
from config import PHOTO_MAX_WORKERS, TEXT_MAX_WORKERS, POST_DETAIL_REQUEST_DELAY

def _extract_photo_links(post_detail_json):
    """Extracts photo links from post data, including gift content if available."""
    try:
        # 普通图片链接
        photo_links_str = post_detail_json["response"]["posts"][0]["post"].get("photoLinks", "[]")
        photos = json.loads(photo_links_str)
        photo_links = [p.get("raw") or p.get("orign") for p in photos if isinstance(p, dict)]
        
        # 检查是否有付费彩蛋图片
        if has_gift_content(post_detail_json):
            # 使用resolve_picture函数获取包含所有图片的列表
            all_photo_links_str = resolve_picture(post_detail_json)
            all_photo_links = json.loads(all_photo_links_str)
            return all_photo_links
        else:
            return photo_links
    except (json.JSONDecodeError, KeyError):
        return []

def _convert_html_to_text(html_content):
    """Converts HTML content to a simplified plain text format."""
    if not html_content:
        return ""
    text = html.unescape(html_content)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def download_photos_for_post(client: LofterClient, post_detail_json, save_dir, base_filename, source_type="tag", tag=""):
    """Downloads all photos for a given post, including gift content photos."""
    photo_links = _extract_photo_links(post_detail_json)
    if not photo_links:
        return []

    # Determine photo save directory based on source_type using path manager
    # Convert legacy source_type to new mode names
    if source_type == "tag-tag":
        mode = "tag"
    elif source_type == "collection-collection":
        mode = "collection"
    elif source_type in ["blog", "subscription"]:
        mode = "blog"
    else:
        # For other source types, use the first part of the source_type
        mode = source_type.split("-")[0] if "-" in source_type else source_type

    # Only create photo directory if there are photos to download
    downloaded_paths = []
    
    # Create photo directory only if we have photos to download
    if photo_links:
        photo_save_dir = path_manager.get_photo_dir(mode, tag)
    
        with concurrent.futures.ThreadPoolExecutor(max_workers=PHOTO_MAX_WORKERS) as executor:
            future_to_url = {}
            for i, url in enumerate(photo_links):
                extension = os.path.splitext(urlparse(url).path)[1].lower() or ".jpg"
                filename = f"{base_filename} ({i+1}){extension}"
                filepath = os.path.join(photo_save_dir, filename)
                future_to_url[executor.submit(client.download_photo, url, filepath)] = url

            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                if result:
                    downloaded_paths.append(result)
    
    return downloaded_paths

def save_post_as_txt(post_detail_json, tag, base_filename, photo_paths, comments_text, source_type="tag"):
    """Saves the processed post content as a TXT file."""
    # Determine the output subdirectory based on source_type using path manager
    # Convert legacy source_type to new mode names
    if source_type == "tag-tag":
        mode = "tag"
    elif source_type == "collection-collection":
        mode = "collection"
    elif source_type in ["blog", "subscription"]:
        mode = "blog"
    else:
        # For other source types, use the first part of the source_type
        mode = source_type.split("-")[0] if "-" in source_type else source_type

    save_dir = path_manager.get_output_dir(mode, tag)
    filepath = os.path.join(save_dir, f"{base_filename}.txt")

    post = post_detail_json["response"]["posts"][0]["post"]
    title = post.get("title", "Untitled")
    publish_time = datetime.fromtimestamp(post["publishTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
    author = post["blogInfo"].get("blogNickName", "Unknown Author")
    blog_id = post["blogInfo"].get("blogId", "Unknown ID")
    blog_url = post.get("blogPageUrl", "")
    post_tags = ", ".join(post.get("tagList", []))
    
    content = ""
    if post.get("type") == 1:
        # 使用resolve_article函数处理包含付费彩蛋的文章内容
        resolved_content = resolve_article(post_detail_json)
        content = _convert_html_to_text(resolved_content or post.get("content", ""))
    elif post.get("type") == 2:
        content = "[Photo Post]\nDownloaded images:\n" + "\n".join(photo_paths) if photo_paths else "[No images found]"

    with open(filepath, 'w', encoding='utf-8') as f:
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

def process_post(client: LofterClient, post_meta, tag, download_comments=False, source_type="tag", name_prefix=None, download_images=True):
    """Fetches full details for a post, downloads content, and saves it."""
    post_detail_json = client.fetch_post_detail(post_meta)
    if not post_detail_json or "response" not in post_detail_json or not post_detail_json["response"].get("posts"):
        print(f"\nFailed to fetch details for post ID {post_meta['postData']['postView']['id']}")
        return

    # 添加请求延迟，避免请求过于频繁
    time.sleep(POST_DETAIL_REQUEST_DELAY)

    post = post_detail_json["response"]["posts"][0]["post"]
    title = post.get("title", "Untitled")
    author = post["blogInfo"].get("blogNickName", "Unknown Author")
    
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
    safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
    base_filename = f"({safe_title} by {safe_author})"
    if name_prefix:
        base_filename = f"{name_prefix} {base_filename}"

    # Convert legacy source_type to new mode names for JSON storage
    if source_type == "tag-tag":
        mode = "tag"
    elif source_type == "collection-collection":
        mode = "collection"
    elif source_type in ["blog", "subscription"]:
        mode = "blog"
    else:
        # For other source types, use the first part of the source_type
        mode = source_type.split("-")[0] if "-" in source_type else source_type

    json_dir = path_manager.get_json_dir(mode, tag, "blog")
    with open(os.path.join(json_dir, f"{base_filename}.json"), 'w', encoding='utf-8') as f:
        json.dump(post_detail_json, f, ensure_ascii=False, indent=4)

    local_photo_paths = []
    if post.get("type") == 2 and download_images:
        # 使用更新的图片提取函数来获取包含付费图片的链接
        local_photo_paths = download_photos_for_post(client, post_detail_json, "", base_filename, source_type, tag)

    comments_text = ""
    if download_comments:
        from processors.comment_processor import process_comments
        post_id = post.get('id')
        blog_id = post.get('blogInfo', {}).get('blogId')
        if post_id and blog_id:
            # 根据source_type确定模式
            mode = source_type.split("-")[0] if "-" in source_type else source_type
            mode = "blog" if mode in ["blog", "subscription"] else mode
            mode = "tag" if mode == "tag-tag" else mode
            mode = "collection" if mode == "collection-collection" else mode
            comments_text = process_comments(client, post_id, blog_id, mode=mode, name=tag)
            # Save comments to the appropriate directory (only in json for non-comment modes)
            # Convert legacy source_type to new mode names for comment storage
            if source_type == "tag-tag":
                mode = "tag"
            elif source_type == "collection-collection":
                mode = "collection"
            elif source_type in ["blog", "subscription"]:
                mode = "blog"
            else:
                # For other source types, use the first part of the source_type
                mode = source_type.split("-")[0] if "-" in source_type else source_type

            comments_dir = path_manager.get_json_dir(mode, tag, "comments")
            comments_file_path = os.path.join(comments_dir, f"{base_filename}_comments.txt")
            with open(comments_file_path, 'w', encoding='utf-8') as f:
                f.write(comments_text)

    save_post_as_txt(post_detail_json, tag, base_filename, local_photo_paths, comments_text, source_type)