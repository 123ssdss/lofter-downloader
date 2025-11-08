import argparse

import time

from network import LofterClient

from utils import format_time
from utils.logger import BeautifulLogger, StatusDisplay

from processors.tag_processor import TagProcessor

from processors.blog_processor import BlogProcessor

from processors.collection_processor import CollectionProcessor

from processors.subscription_processor import SubscriptionProcessor

from processors.comment_mode_processor import CommentModeProcessor

from config import DEFAULT_LIST_TYPE, DEFAULT_TIME_LIMIT, DEFAULT_BLOG_TYPE


def main():
    parser = argparse.ArgumentParser(description="Lofter Crawler")
    parser.add_argument("mode", choices=["tag", "blog", "comment", "collection", "subscription"], 
                       help="The mode to run the crawler in.")
    parser.add_argument("value", nargs='*', default=None, 
                       help="The value for the selected mode (e.g., tag name(s), post ID, collection ID). Not used for subscription.")
    parser.add_argument("--blog_id", help="The blog ID (required for 'blog' and 'comment' modes).")
    parser.add_argument("--list_type", default=DEFAULT_LIST_TYPE, help="List type for tag mode.")

    parser.add_argument("--timelimit", default=DEFAULT_TIME_LIMIT, help="Time limit for tag mode.")

    parser.add_argument("--blog_type", default=DEFAULT_BLOG_TYPE, help="Blog type for tag mode.")
    parser.add_argument("--no-comments", action="store_true", help="Disable comment downloading.")
    parser.add_argument("--no-photos", action="store_true", help="Disable photo downloading.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    
    args = parser.parse_args()

    # 构建标题信息
    title_info = {
        "运行模式": args.mode,
        "调试模式": "启用" if args.debug else "禁用"
    }
    
    if args.value:
        if isinstance(args.value, list) and len(args.value) > 0:
            title_info["参数值"] = ", ".join(str(v) for v in args.value)
        elif isinstance(args.value, str):
            title_info["参数值"] = args.value
    
    if args.blog_id:
        title_info["博客ID"] = args.blog_id
    
    if args.mode == "tag":
        title_info["列表类型"] = args.list_type
        if args.timelimit:
            title_info["时间限制"] = args.timelimit
        title_info["博客类型"] = args.blog_type
    
    title_info["评论下载"] = "禁用" if args.no_comments else "启用"
    title_info["图片下载"] = "禁用" if args.no_photos else "启用"
    
    StatusDisplay.print_header("Lofter 爬虫工具", title_info)
    
    client = LofterClient(debug=args.debug)
    
    start_time = time.time()
    result = {}

    try:
        if args.mode == "tag":
            # 处理标签模式
            tags = args.value if isinstance(args.value, list) else [args.value] if args.value else []
            if not tags or (len(tags) == 1 and tags[0] is None):
                StatusDisplay.print_error("标签模式需要至少一个标签名称")
                return
            
            tag_processor = TagProcessor(client, args.debug)
            result = tag_processor.process(
                tags=tags,
                list_type=args.list_type,
                timelimit=args.timelimit,
                blog_type=args.blog_type,
                download_comments=not args.no_comments,
                download_images=not args.no_photos
            )
        
        elif args.mode == "blog":
            # 处理博客模式
            post_id = args.value[0] if args.value else None
            if not post_id:
                StatusDisplay.print_error("博客模式需要提供帖子ID或URL")
                return
            
            # 去除可能的引号
            post_id = post_id.strip('"\'')
            
            # 如果post_id是URL，则不需要--blog_id参数
            is_url = post_id.startswith("http://") or post_id.startswith("https://")
            if not is_url and not args.blog_id:
                StatusDisplay.print_error("非URL模式下需要提供 --blog_id 参数")
                return
            
            blog_processor = BlogProcessor(client, args.debug)
            result = blog_processor.process(
                post_id=post_id,
                blog_id=args.blog_id,
                download_comments=True,  # 博客模式总是下载评论
                download_images=not args.no_photos
            )

        elif args.mode == "comment":
            # 处理评论模式
            if not args.blog_id or not args.value:
                StatusDisplay.print_error("评论模式需要提供帖子ID和 --blog_id 参数")
                return
            
            post_id = args.value[0] if args.value else None
            if not post_id:
                StatusDisplay.print_error("评论模式需要提供帖子ID")
                return
            
            comment_processor = CommentModeProcessor(client, args.debug)
            result = comment_processor.process(post_id, args.blog_id)

        elif args.mode == "collection":
            # 处理合集模式
            if not args.value:
                StatusDisplay.print_error("合集模式需要提供合集ID")
                return
            
            collection_id = args.value[0] if args.value else None
            if not collection_id:
                StatusDisplay.print_error("合集模式需要提供合集ID")
                return
            
            collection_processor = CollectionProcessor(client, args.debug)
            result = collection_processor.process(
                collection_id=collection_id,
                download_comments=not args.no_comments,
                download_images=not args.no_photos
            )

        elif args.mode == "subscription":
            # 处理订阅模式
            subscription_processor = SubscriptionProcessor(client, args.debug)
            result = subscription_processor.process()

    except KeyboardInterrupt:
        StatusDisplay.print_warning("操作被用户中断")
        return
    except Exception as e:
        StatusDisplay.print_error(f"处理过程中发生错误: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return

    # 显示处理结果
    total_time = time.time() - start_time
    
    StatusDisplay.print_header("爬取完成")
    StatusDisplay.print_info(f"总用时: {format_time(total_time)}")
    
    if result:
        if result.get("success"):
            StatusDisplay.print_success("所有任务处理成功!")
            
            # 根据不同模式显示详细信息
            StatusDisplay.print_section("处理详情")
            if args.mode == "tag":
                StatusDisplay.print_info(f"标签处理: {result.get('processed_tags', 0)}/{result.get('total_tags', 0)}")
                StatusDisplay.print_info(f"帖子处理: {result.get('total_posts_processed', 0)} 成功, {result.get('total_posts_failed', 0)} 失败")
                
            elif args.mode == "blog":
                if result.get("processed_files"):
                    StatusDisplay.print_info(f"文件保存: {len(result['processed_files'])} 个")
                    
            elif args.mode == "collection":
                StatusDisplay.print_info(f"合集名称: {result.get('collection_name', 'Unknown')}")
                StatusDisplay.print_info(f"帖子处理: {result.get('processed_posts', 0)}/{result.get('total_posts', 0)}")
                
            elif args.mode == "subscription":
                StatusDisplay.print_info(f"订阅总数: {result.get('total_subscriptions', 0)}")
                StatusDisplay.print_info(f"未读数量: {result.get('total_unread', 0)}")
                
            elif args.mode == "comment":
                StatusDisplay.print_info(f"帖子ID: {result.get('post_id', 'Unknown')}")
                StatusDisplay.print_info(f"评论处理: {result.get('comments_count', 0)} 条")
        else:
            StatusDisplay.print_error("处理失败")
            StatusDisplay.print_error(f"错误信息: {result.get('error', '未知错误')}")
    else:
        StatusDisplay.print_warning("没有返回结果")
    
    print("=" * 60)


if __name__ == "__main__":
    main()