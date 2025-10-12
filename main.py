import argparse
import time
import os
from network import LofterClient
import json
from processors.tag_processor import process_tag
from processors.blog_processor import process_post
from processors.comment_processor import process_comments
from processors.collection_processor import process_collection
from processors.subscription_processor import process_subscription
from processors.comment_mode_processor import process_comment_mode
from utils import format_time
from utils.path_manager import path_manager
from utils.cookie_manager import interactive_cookie_setup

def main():
    parser = argparse.ArgumentParser(description="Lofter Crawler")
    parser.add_argument("mode", choices=["tag", "blog", "comment", "collection", "subscription", "cookie_setup"], help="The mode to run the crawler in.")
    parser.add_argument("value", nargs='*', default=None, help="The value for the selected mode (e.g., tag name(s), post ID, collection ID). Not used for subscription.")
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
        interactive_cookie_setup()
        return

    # Load cookies from cookie.json file using the cookie manager
    from utils.cookie_manager import load_cookies
    cookie_config = load_cookies()
    cookies = cookie_config.get("cookies", {})
    selected_cookie_type = cookie_config.get("selected_cookie_type", None)
    
    # Check if cookies.json exists and has valid cookie values
    if not any(cookies.values()):
        print("Warning: No cookie values found in cookie.json. Subscription mode will not work.")
        print("Use 'python main.py cookie_setup' to set up your cookies.")

    # Use all cookies for the client initialization, regardless of selected_cookie_type
    # This ensures all authentication tokens are available for different API calls
    config = {
        "cookies": cookies,
        "debug": args.debug
    }

    print("--- Lofter Crawler ---")
    if selected_cookie_type:
        print(f"Using cookie type: {selected_cookie_type}")
    
    client = LofterClient(cookies=config["cookies"], debug=config["debug"])
    
    start_time = time.time()

    if args.mode == "tag":
        # Handle both single tag and multiple tags
        tags = args.value if isinstance(args.value, list) else [args.value] if args.value else []
        if not tags or (len(tags) == 1 and tags[0] is None):
            print("Error: At least one tag name is required for tag mode.")
            return
        print(f"Mode: Tag | Values: {tags}")
        # Don't clear global directories to maintain isolation between different tags/collections
        for tag in tags:
            if tag:  # Only process non-empty tags
                print(f"Processing tag: {tag}")
                process_tag(client, tag, args.list_type, args.timelimit, args.blog_type, not args.no_comments, not args.no_photos)
    
    elif args.mode == "blog":
       if not args.blog_id:
           print("Error: --blog_id is required for blog mode.")
           return
        
       # 从args.value列表中获取post ID（因为nargs='*'返回一个列表）
       post_id = args.value[0] if args.value else None
       if not post_id:
           print("Error: Post ID is required for blog mode.")
           return
           
       print(f"Mode: Blog | Post ID: {post_id} | Blog ID: {args.blog_id}")
       
       # Manually construct the post_meta object
       post_meta = {
           "blogInfo": {"blogId": args.blog_id, "blogName": ""}, # blogName is not strictly necessary for the API call if blogId is present
           "postData": {"postView": {"id": post_id}}
       }
       
       # Don't clear global directories to maintain isolation between different tags/collections
       # For blog mode, always download comments, ignoring the --no-comments flag, but respect --no-photos
       process_post(client, post_meta, "single_post", True, source_type="blog", download_images=not args.no_photos)

    elif args.mode == "comment":
        if not args.blog_id or not args.value:
            print("Error: Both value (post ID) and --blog_id are required for comment mode.")
            return
             
        # 从args.value列表中获取post ID（因为nargs='*'返回一个列表）
        post_id = args.value[0] if args.value else None
        if not post_id:
            print("Error: Post ID is required for comment mode.")
            return
             
        print(f"Mode: Comment | Post ID: {post_id} | Blog ID: {args.blog_id}")
        # Use the new comment mode processor for proper isolation
        process_comment_mode(client, post_id, args.blog_id)

    elif args.mode == "collection":
        if not args.value:
            print("Error: A value (collection ID) is required for collection mode.")
            return
             
        # 从args.value列表中获取collection ID（因为nargs='*'返回一个列表）
        collection_id = args.value[0] if args.value else None
        if not collection_id:
            print("Error: Collection ID is required for collection mode.")
            return
             
        print(f"Mode: Collection | ID: {collection_id}")
        # Don't clear global directories to maintain isolation between different tags/collections
        process_collection(client, collection_id, not args.no_comments, not args.no_photos)

    elif args.mode == "subscription":
        print("Mode: Subscription")
            
        # Call the subscription processor instead of fetching posts directly
        # The authentication keys will be handled internally by the LofterClient
        process_subscription(client, not args.no_comments)
        return

    total_time = time.time() - start_time
    print("\n" + "=" * 50)
    print("Crawling finished!")
    print(f"Total time: {format_time(total_time)}")
    print("=" * 50)

if __name__ == "__main__":
    main()