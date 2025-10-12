from network import LofterClient
import json
from datetime import datetime
from utils.path_manager import path_manager

def _format_comment_new(comment, indent_level=0, is_reply=False):
    """Formats a single comment dictionary into the new format."""
    indent = "    " * indent_level
    author = comment.get("author", {}).get("blogNickName", "Unknown")
    content = comment.get('content', '').strip()
    publish_time = comment.get('publishTimeFormatted', '')
    like_count = comment.get('likeCount', 0)
    ip_location = comment.get('ipLocation', '')
    
    result = ""
    result += f"{indent}----------\n"
    
    # Use different labels for replies vs main comments
    if is_reply:
        result += f"{indent}    回复人：{author}\n"
    else:
        result += f"{indent}发布人：{author}\n"
    
    result += f"{indent}内容：{content}\n"
    result += f"{indent}时间：{publish_time}\n"
    result += f"{indent}点赞数：{like_count}\n"
    
    # Add IP location if available
    if ip_location:
        result += f"{indent}IP位置：{ip_location}\n"
    
    return result

def _format_replies(replies, indent_level=1):
    """Formats a list of replies."""
    result = ""
    for idx, reply in enumerate(replies, 1):
        # Format the reply with the correct indentation - replies are L2, L3, etc. depending on context
        result += f"{'    ' * indent_level}---------- (L{indent_level + 1}-{idx})\n"
        result += f"{'    ' * (indent_level + 1)}回复人：{reply.get('author', {}).get('blogNickName', 'Unknown')}\n"
        result += f"{'    ' * (indent_level + 1)}内容：{reply.get('content', '').strip()}\n"
        result += f"{'    ' * (indent_level + 1)}时间：{reply.get('publishTimeFormatted', '')}\n"
        result += f"{'    ' * (indent_level + 1)}点赞数：{reply.get('likeCount', 0)}\n"
        result += "\n"  # Add a newline after each reply
    return result

def _group_comments_by_quote(comments_data):
    """Group comments by their quote content."""
    grouped = {}
    non_quoted = []
    
    for comment in comments_data:
        quote = comment.get('quote', '').strip()
        if quote:
            if quote not in grouped:
                grouped[quote] = []
            grouped[quote].append(comment)
        else:
            non_quoted.append(comment)
    
    return grouped, non_quoted


def _format_comments_recursive(comments_data, indent_level=0):
    """Recursively formats comments and their replies into the new format."""
    result = ""
    
    # Group comments by quote
    grouped_comments, non_quoted_comments = _group_comments_by_quote(comments_data)
    
    # Process grouped comments (those with quotes)
    for quote, comments_list in grouped_comments.items():
        result += f"----------({quote})----------\n"
        
        # Process each comment in the group
        for idx, comment in enumerate(comments_list, 1):
            result += f"---------- (L{indent_level}-{idx})\n"
            result += _format_comment_new(comment, indent_level, is_reply=False)
            
            # Add replies section if there are replies
            replies = comment.get('replies', [])
            if replies:
                result += f"\n{'    ' * indent_level}---回复列表---\n"
                result += _format_replies(replies, indent_level + 1)
            
            result += "\n"  # Add a newline after each comment block
    
    # Process non-quoted comments
    for idx, comment in enumerate(non_quoted_comments, 1):
        result += f"---------- (L{indent_level}-{idx})\n"
        result += _format_comment_new(comment, indent_level, is_reply=False)
        
        # Add replies section if there are replies
        replies = comment.get('replies', [])
        if replies:
            result += f"\n{'    ' * indent_level}---回复列表---\n"
            result += _format_replies(replies, indent_level + 1)
        
        result += "\n"  # Add a newline after each comment block
    
    return result

def process_comments(client: LofterClient, post_id, blog_id, mode='comment', name=''):
    """Fetches and formats all comments for a post by calling the client method."""
    # Get the structured comment data from the client with return_structure=True
    structured_comments = client.fetch_all_comments_for_post(post_id, blog_id, return_structure=True, mode=mode, name=name)
    
    # 检查返回的数据结构是新的还是旧的
    if isinstance(structured_comments, dict) and "hot_list" in structured_comments and "all_list" in structured_comments:
        # 新结构: 包含hot_list和all_list
        result = "[热门评论]\n"
        result += _format_comments_recursive(structured_comments["hot_list"])
        result += "\n[全部评论]\n"
        result += _format_comments_recursive(structured_comments["all_list"])
        return result
    else:
        # 旧结构: 直接处理列表
        return _format_comments_recursive(structured_comments)