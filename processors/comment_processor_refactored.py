"""
评论处理器（重构版本）
整合评论获取、格式化和保存功能
"""
from network import LofterClient
from processors.comment_fetcher import CommentFetcher
from processors.comment_formatter import CommentFormatter
from processors.comment_saver import CommentSaver


def process_comments(
    client: LofterClient, 
    post_id: str, 
    blog_id: str, 
    mode: str = 'comment', 
    name: str = ''
) -> str:
    """
    处理评论的主函数
    
    Args:
        client: LofterClient实例
        post_id: 帖子ID
        blog_id: 博客ID
        mode: 模式 ('tag', 'collection', 'blog', 'comment', 'subscription')
        name: 名称（标签名、收藏集名等）
        
    Returns:
        格式化后的评论文本
    """
    # 创建处理器实例
    fetcher = CommentFetcher(client)
    formatter = CommentFormatter()
    saver = CommentSaver(client)
    
    # 获取评论数据
    structured_comments = fetcher.fetch_all_comments(post_id, blog_id)
    
    # 检查是否有评论
    if not structured_comments or not structured_comments.get("all_list"):
        return ""
    
    # 保存评论到文件
    saver.save_comments(post_id, blog_id, structured_comments, mode, name)
    
    # 格式化评论为文本
    formatted_text = formatter.format_comments(structured_comments)
    
    return formatted_text
