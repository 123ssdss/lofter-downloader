import time
from network import LofterClient
from processors.blog_processor import process_post
from utils import display_progress
from utils.path_manager import path_manager
from config import TAG_POST_REQUEST_DELAY

def process_tag(client: LofterClient, tag, list_type, timelimit, blog_type, download_comments, download_images=True):
    """Processes all posts for a given tag."""
    posts = client.fetch_posts_by_tag(tag, list_type, timelimit, blog_type)
    total_posts = len(posts)
    
    if total_posts == 0:
        print(f"No posts found for tag '{tag}'.")
        return

    print(f"\nProcessing {total_posts} posts for tag '{tag}'...")
    start_time = time.time()
    
    for i, post_meta in enumerate(posts):
        display_progress(i + 1, total_posts, start_time, tag)
        try:
            process_post(client, post_meta, tag, download_comments, source_type="tag-tag", download_images=download_images)
        except Exception as e:
            print(f"\nError processing post {post_meta['postData']['postView']['id']}: {e}")
        time.sleep(TAG_POST_REQUEST_DELAY)

    display_progress(total_posts, total_posts, start_time, f"Tag '{tag}' Complete")