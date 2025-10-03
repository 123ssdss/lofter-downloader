import os
import json
import time
import re
import html
from datetime import datetime
from network import LofterClient
from utils import display_progress
from utils.path_manager import path_manager
from config import COLLECTION_REQUEST_DELAY

def make_valid_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def html_to_text(html_content):
    if not html_content:
        return ""
    text = html.unescape(html_content)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

from processors.blog_processor import process_post

def process_collection(client: LofterClient, collection_id, download_comments, download_images=True):
    """
    Refactored to align with the tag_processor workflow, ensuring comments can be fetched.
    """
    print(f"Fetching collection '{collection_id}'...")
    
    # First, get collection metadata to find the name and total count
    limit_once = 50
    collection_meta = client.get_collection_list(collection_id, offset=0, limit=1)
    
    if not collection_meta or 'collection' not in collection_meta:
        print(f"Could not fetch metadata for collection '{collection_id}'.")
        return

    post_count = collection_meta['collection']['postCount']
    collection_name = make_valid_filename(collection_meta['collection']['name'])
    
    print(f"Collection: '{collection_name}', Posts: {post_count}")

    # Fetch all post items in a loop
    all_post_items = []
    for i in range(0, post_count, limit_once):
        print(f"Fetching posts {i+1}-{min(i+limit_once, post_count)}...")
        response = client.get_collection_list(collection_id, offset=i, limit=limit_once)
        if response and 'items' in response:
            all_post_items.extend(response['items'])
        time.sleep(COLLECTION_REQUEST_DELAY)
        
    if not all_post_items:
        print("No post items found in the collection.")
        return

    # Now, delegate the processing of each post to the robust `process_post` function
    start_time = time.time()

    for i, post_item in enumerate(all_post_items):
        display_progress(i + 1, post_count, start_time, collection_name)
        
        # This is the crucial adaptation. The collection API's item structure
        # must be converted to the `post_meta` structure that `process_post` expects.
        post_data = post_item.get("post", {})
        blog_info = post_item.get("blogInfo", {})

        # Ensure that blogId from the post object is prioritized if available
        if 'blogId' in post_data and 'blogInfo' in post_data:
             blog_info = post_data['blogInfo']
        
        adapted_post_meta = {
            "blogInfo": blog_info,
            "postData": {
                "postView": post_data
            }
        }
        
        try:
            # Add the post index as a prefix for the filename
            name_prefix = str(i + 1)
            process_post(client, adapted_post_meta, collection_name, download_comments, source_type="collection-collection", name_prefix=name_prefix, download_images=download_images)
        except Exception as e:
            post_id = post_item.get("post", {}).get("id", "N/A")
            print(f"\nError processing post {post_id} from collection: {e}")
        
    print(f"\nSuccessfully processed {len(all_post_items)} posts from collection '{collection_name}'.")