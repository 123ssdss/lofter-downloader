import re


def extract_ids_from_html(html_content, url=None):
    """
    从Lofter页面的HTML内容中提取Blog ID和Post ID
    
    Args:
        html_content (str): Lofter页面的HTML内容
        url (str): 原始URL，用于备用解析
        
    Returns:
        dict: 包含post_id和blog_id的字典，如果无法解析则返回None
    """
    try:
        # 如果有HTML内容，尝试从中提取信息
        if html_content and html_content.strip():
            # 查找包含postId和blogId的iframe标签
            # 匹配模式: <iframe id="control_frame" ... src="//www.lofter.com/control?blogId=817482179&postId=11794513301"></iframe>
            # 支持相对协议(//)和完整协议(https://或http://)
            control_frame_pattern = r'<iframe[^>]*id="control_frame"[^>]*src="[^"]*(?:https?://)?(?:www\.)?lofter\.com/control\?blogId=(\d+)&postId=(\d+)"[^>]*>'
            match = re.search(control_frame_pattern, html_content)
            
            if match:
                blog_id = match.group(1)
                post_id = match.group(2)
                print(f"从control_frame成功提取: blog_id={blog_id}, post_id={post_id}")
                return {
                    'post_id': post_id,
                    'blog_id': blog_id,
                    'source': 'html_control_frame'
                }
            
            # 如果没有找到control_frame，尝试查找其他可能包含ID的iframe标签
            # 查找可能包含blogId和postId的任何iframe的src属性
            iframe_src_pattern = r'<iframe[^>]*src="[^"]*blogId=(\d+)[^"]*postId=(\d+)"[^>]*>'
            match = re.search(iframe_src_pattern, html_content)
            
            if match:
                blog_id = match.group(1)
                post_id = match.group(2)
                print(f"从iframe src中提取: blog_id={blog_id}, post_id={post_id}")
                return {
                    'post_id': post_id,
                    'blog_id': blog_id,
                    'source': 'html_iframe_src'
                }
            
            # 尝试从页面URL中提取
            # 查找包含post链接的标签
            post_url_pattern = r'https://[^.]+\.lofter\.com/post/([a-f0-9]+_[a-f0-9]+)'
            match = re.search(post_url_pattern, html_content)
            
            if match:
                post_url_id = match.group(1)
                # 如果从URL中提取到post_id，尝试从其他地方获取blog_id
                # 查找博客名称
                blog_name_pattern = r'https://([^.]+)\.lofter\.com/'
                blog_match = re.search(blog_name_pattern, html_content)
                
                if blog_match:
                    blog_name = blog_match.group(1)
                    print(f"从HTML页面中提取: post_id={post_url_id}, blog_name={blog_name}")
                    return {
                        'post_id': post_url_id,
                        'blog_name': blog_name,
                        'source': 'html_post_url'
                    }
            
            # 查找其他可能包含ID的iframe标签
            # 尝试匹配comment_frame中的ID
            comment_frame_pattern = r'<iframe[^>]*id="comment_frame"[^>]*src="[^"]*pid=(\d+)&bid=(\d+)"[^>]*>'
            match = re.search(comment_frame_pattern, html_content)
            
            if match:
                post_id = match.group(1)
                blog_id = match.group(2)
                return {
                    'post_id': post_id,
                    'blog_id': blog_id,
                    'source': 'html_comment_frame'
                }
        else:
            print("HTML内容为空，无法进行HTML解析")
        
        # HTML解析失败，无法提取信息
        if url:
            print("HTML解析失败，无法提取信息")
                
    except Exception as e:
        print(f"从HTML中提取ID时出错: {e}")
        
    return None





