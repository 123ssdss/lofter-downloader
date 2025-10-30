import argparse
import time
from network import LofterClient
from utils import format_time
from utils.cookie_manager import load_cookies
from processors.tag_processor import TagProcessor
from processors.blog_processor import BlogProcessor
from processors.collection_processor import CollectionProcessor
from processors.subscription_processor import SubscriptionProcessor
from processors.comment_mode_processor import CommentModeProcessor


def main():
    parser = argparse.ArgumentParser(description="Lofter Crawler")
    parser.add_argument("mode", choices=["tag", "blog", "comment", "collection", "subscription", "cookie_setup"], 
                       help="The mode to run the crawler in.")
    parser.add_argument("value", nargs='*', default=None, 
                       help="The value for the selected mode (e.g., tag name(s), post ID, collection ID). Not used for subscription.")
    parser.add_argument("--blog_id", help="The blog ID (required for 'blog' and 'comment' modes).")
    parser.add_argument("--list_type", default="total", help="List type for tag mode.")
    parser.add_argument("--timelimit", default="", help="Time limit for tag mode.")
    parser.add_argument("--blog_type", default="1", help="Blog type for tag mode.")
    parser.add_argument("--no-comments", action="store_true", help="Disable comment downloading.")
    parser.add_argument("--no-photos", action="store_true", help="Disable photo downloading.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    
    args = parser.parse_args()
    
    # 如果选择的是 cookie_setup 模式，运行 cookie 设置向导
    if args.mode == "cookie_setup":
        from utils.cookie_manager import interactive_cookie_setup
        interactive_cookie_setup()
        return

    # 加载cookies
    cookie_config = load_cookies()
    cookies = cookie_config.get("cookies", {})
    selected_cookie_type = cookie_config.get("selected_cookie_type", None)
    
    # 检查cookies是否存在
    if not any(cookies.values()):
        print("Warning: No cookie values found in cookie.json. Subscription mode will not work.")
        print("Use 'python main.py cookie_setup' to set up your cookies.")

    # 初始化客户端
    config = {
        "cookies": cookies,
        "debug": args.debug
    }

    print("--- Lofter Crawler ---")
    if selected_cookie_type:
        print(f"Using cookie type: {selected_cookie_type}")
    
    client = LofterClient(debug=config["debug"])
    
    start_time = time.time()
    result = {}

    try:
        if args.mode == "tag":
            # 处理标签模式
            tags = args.value if isinstance(args.value, list) else [args.value] if args.value else []
            if not tags or (len(tags) == 1 and tags[0] is None):
                print("Error: At least one tag name is required for tag mode.")
                return
            
            print(f"Mode: Tag | Values: {tags}")
            
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
            if not args.blog_id:
                print("Error: --blog_id is required for blog mode.")
                return
            
            post_id = args.value[0] if args.value else None
            if not post_id:
                print("Error: Post ID is required for blog mode.")
                return
            
            print(f"Mode: Blog | Post ID: {post_id} | Blog ID: {args.blog_id}")
            
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
                print("Error: Both value (post ID) and --blog_id are required for comment mode.")
                return
            
            post_id = args.value[0] if args.value else None
            if not post_id:
                print("Error: Post ID is required for comment mode.")
                return
            
            print(f"Mode: Comment | Post ID: {post_id} | Blog ID: {args.blog_id}")
            
            comment_processor = CommentModeProcessor(client, args.debug)
            result = comment_processor.process(post_id, args.blog_id)

        elif args.mode == "collection":
            # 处理合集模式
            if not args.value:
                print("Error: A value (collection ID) is required for collection mode.")
                return
            
            collection_id = args.value[0] if args.value else None
            if not collection_id:
                print("Error: Collection ID is required for collection mode.")
                return
            
            print(f"Mode: Collection | ID: {collection_id}")
            
            collection_processor = CollectionProcessor(client, args.debug)
            result = collection_processor.process(
                collection_id=collection_id,
                download_comments=not args.no_comments,
                download_images=not args.no_photos
            )

        elif args.mode == "subscription":
            # 处理订阅模式
            print("Mode: Subscription")
            
            subscription_processor = SubscriptionProcessor(client, args.debug)
            result = subscription_processor.process()

    except KeyboardInterrupt:
        print("\n操作被用户中断")
        return
    except Exception as e:
        print(f"Error during processing: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return

    # 显示处理结果
    total_time = time.time() - start_time
    print("\n" + "=" * 50)
    print("Crawling finished!")
    print(f"Total time: {format_time(total_time)}")
    
    if result:
        if result.get("success"):
            print("✓ Processing completed successfully")
            
            # 根据不同模式显示详细信息
            if args.mode == "tag":
                print(f"Processed tags: {result.get('processed_tags', 0)}/{result.get('total_tags', 0)}")
                print(f"Total posts processed: {result.get('total_posts_processed', 0)}")
                print(f"Total posts failed: {result.get('total_posts_failed', 0)}")
                
            elif args.mode == "blog":
                if result.get("processed_files"):
                    print(f"Files saved: {len(result['processed_files'])}")
                    
            elif args.mode == "collection":
                print(f"Collection: {result.get('collection_name', 'Unknown')}")
                print(f"Posts processed: {result.get('processed_posts', 0)}/{result.get('total_posts', 0)}")
                
            elif args.mode == "subscription":
                print(f"Total subscriptions: {result.get('total_subscriptions', 0)}")
                print(f"Total unread: {result.get('total_unread', 0)}")
                
            elif args.mode == "comment":
                print(f"Post ID: {result.get('post_id', 'Unknown')}")
                print(f"Comments processed: {result.get('comments_count', 0)}")
        else:
            print("✗ Processing failed")
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("=" * 50)


if __name__ == "__main__":
    main()