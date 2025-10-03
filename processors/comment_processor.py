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

def _format_comments_recursive(comments_data, indent_level=0):
    """Recursively formats comments and their replies into the new format."""
    result = ""
    
    for idx, comment in enumerate(comments_data, 1):
        quote = comment.get('quote', '')
        
        # Add quote if exists
        if quote:
            result += f"----------({quote})---------- (L{indent_level}-{idx})\n"
            result += _format_comment_new(comment, indent_level, is_reply=False)
        else:
            result += f"---------- (L{indent_level}-{idx})\n"
            # Format the main comment
            result += _format_comment_new(comment, indent_level, is_reply=False)
        
        # Add replies section if there are replies
        replies = comment.get('replies', [])
        if replies:
            result += f"\n{'    ' * indent_level}---回复列表---\n"
            result += _format_replies(replies, indent_level + 1)
        
        result += "\n"  # Add a newline after each comment block
    
    return result

def process_comments(client: LofterClient, post_id, blog_id):
    """Fetches and formats all comments for a post by calling the client method."""
    # Get the structured comment data from the client with return_structure=True
    structured_comments = client.fetch_all_comments_for_post(post_id, blog_id, return_structure=True)
    # Format the structured data using our new format
    return _format_comments_recursive(structured_comments)