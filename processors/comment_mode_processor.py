import os
import time
from network import LofterClient
from utils import display_progress
from utils.path_manager import path_manager


def process_comment_mode(client: LofterClient, post_url_or_id, blog_id=None):
    """
    专门用于处理单个帖子评论的模式
    """
    print(f"开始处理评论模式，帖子: {post_url_or_id}")
    
    # 如果提供的是URL，尝试从中提取post_id和blog_id
    if post_url_or_id.startswith('http'):
        # 从URL中提取post_id和blog_id的逻辑
        # 这里假设URL格式为 https://xx.lofter.com/post/xxx 或其他格式
        post_id = extract_post_id_from_url(post_url_or_id)
        if not blog_id:
            blog_id = extract_blog_id_from_url(post_url_or_id)
    else:
        # 假设直接提供的是post_id
        post_id = post_url_or_id

    if not post_id:
        print("无法提取到有效的post_id")
        return

    if not blog_id:
        print("需要提供blog_id")
        return
    
    # 获取帖子详细信息
    post_detail = client.fetch_post_detail_by_id(post_id, blog_id)
    
    if not post_detail or "response" not in post_detail or not post_detail["response"].get("posts"):
        print(f"无法获取帖子详情: {post_id}")
        return

    post = post_detail["response"]["posts"][0]["post"]
    title = post.get("title", "Untitled")
    author = post["blogInfo"].get("blogNickName", "Unknown Author")
    
    # 创建安全的文件名
    import re
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:100]
    safe_author = re.sub(r'[\\/*?:"<>|]', '_', author)
    base_filename = f"({safe_title} by {safe_author})"
    
    # 保存帖子的JSON数据到comment模式的目录
    json_dir = path_manager.get_json_dir('comment', 'posts', 'blog')
    json_file_path = os.path.join(json_dir, f"{base_filename}.json")
    
    os.makedirs(json_dir, exist_ok=True)
    with open(json_file_path, 'w', encoding='utf-8') as f:
        import json
        json.dump(post_detail, f, ensure_ascii=False, indent=4)
    
    # 获取评论
    from processors.comment_processor import process_comments
    comments_text = process_comments(client, post_id, blog_id, mode='comment')
    
    # 保存评论到comment模式的目录
    comments_dir = path_manager.get_json_dir('comment', 'posts', 'comments')
    comments_file_path = os.path.join(comments_dir, f"{base_filename}_comments.txt")
    
    os.makedirs(comments_dir, exist_ok=True)
    with open(comments_file_path, 'w', encoding='utf-8') as f:
        f.write(comments_text)
    
    # 保存帖子内容到输出目录
    output_dir = path_manager.get_output_dir('comment', 'posts')
    output_file_path = os.path.join(output_dir, f"{base_filename}.txt")
    
    save_post_as_txt(post, base_filename, comments_text, output_file_path)
    
    print(f"评论模式处理完成: {base_filename}")


def extract_post_id_from_url(url):
    """从URL中提取post_id"""
    import re
    # 尝试匹配不同格式的URL
    patterns = [
        r'/post/([a-zA-Z0-9]+)',  # /post/postId
        r'/post/([a-zA-Z0-9]+)\?',  # /post/postId?param=value
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def extract_blog_id_from_url(url):
    """从URL中提取blog_id"""
    import re
    # 提取博客名称
    pattern = r'//(.*?)\.lofter\.com'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def save_post_as_txt(post, base_filename, comments_text, filepath):
    """保存帖子内容到txt文件"""
    import re
    from datetime import datetime
    import html

    def _convert_html_to_text(html_content):
        """Converts HTML content to a simplified plain text format."""
        if not html_content:
            return ""
        text = html.unescape(html_content)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    title = post.get("title", "Untitled")
    publish_time = datetime.fromtimestamp(post["publishTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
    author = post["blogInfo"].get("blogNickName", "Unknown Author")
    blog_id = post["blogInfo"].get("blogId", "Unknown ID")
    blog_url = post.get("blogPageUrl", "")
    post_tags = ", ".join(post.get("tagList", []))
    
    content = ""
    if post.get("type") == 1:
        content = _convert_html_to_text(post.get("content", ""))
    elif post.get("type") == 2:
        content = "[Photo Post with potential images]"

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