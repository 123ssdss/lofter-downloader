import re
from urllib.parse import urlparse


def parse_lofter_url(url):
    """
    解析Lofter URL，提取post_id和blog_id
    
    Args:
        url (str): Lofter URL
        
    Returns:
        dict: 包含post_id和blog_id的字典，如果无法解析则返回None
    """
    try:
        # 去除可能的引号
        url = url.strip('"\'')
        
        # 解析URL
        parsed = urlparse(url)
        
        # 检查是否是Lofter域名
        if not parsed.netloc.endswith('.lofter.com'):
            return None
            
        # 处理不同类型的URL格式
        # 格式1: https://username.lofter.com/post/post_id
        # 格式2: https://www.lofter.com/front/blog/view.do?blogId=xxx&postId=xxx
        
        # 情况1: 标准博客文章URL (如: zuodaoxing.lofter.com/post/30b9c9c3_2bf01fd95)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'post':
            post_id = path_parts[1]
            
            # 从域名中提取blog名称
            blog_name = parsed.netloc.replace('.lofter.com', '')
            if blog_name.startswith('www.'):
                blog_name = blog_name[4:]  # 移除www前缀
                
            return {
                'post_id': post_id,
                'blog_name': blog_name,
                'url_type': 'standard'
            }
            
        # 情况2: 查询参数形式的URL (如: www.lofter.com/front/blog/view.do?blogId=123&postId=456)
        elif 'postId' in parsed.query:
            # 解析查询参数
            query_params = {}
            for param in parsed.query.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value
                    
            post_id = query_params.get('postId')
            blog_id = query_params.get('blogId')
            
            if post_id:
                return {
                    'post_id': post_id,
                    'blog_id': blog_id,
                    'url_type': 'query'
                }
                
        # 情况3: 从完整域名中提取blog信息
        elif len(path_parts) >= 1:
            # 检查是否有post ID在路径中
            for part in path_parts:
                # Lofter的post ID通常是十六进制格式
                if re.match(r'^[0-9a-f]+_[0-9a-f]+$', part):
                    post_id = part
                    blog_name = parsed.netloc.replace('.lofter.com', '')
                    if blog_name.startswith('www.'):
                        blog_name = blog_name[4:]
                        
                    return {
                        'post_id': post_id,
                        'blog_name': blog_name,
                        'url_type': 'embedded'
                    }
                    
    except Exception as e:
        print(f"解析URL时出错: {e}")
        return None
        
    return None


def extract_ids_from_html(html_content):
    """
    从Lofter页面的HTML内容中提取Blog ID和Post ID
    
    Args:
        html_content (str): Lofter页面的HTML内容
        
    Returns:
        dict: 包含post_id和blog_id的字典，如果无法解析则返回None
    """
    try:
        # 查找包含postId和blogId的iframe标签
        # 匹配模式: <iframe id="control_frame" ... src="//www.lofter.com/control?blogId=817482179&postId=11794513301"></iframe>
        control_frame_pattern = r'<iframe[^>]*id="control_frame"[^>]*src="[^"]*lofter\.com/control\?blogId=(\d+)&postId=(\d+)"[^>]*>'
        match = re.search(control_frame_pattern, html_content)
        
        if match:
            blog_id = match.group(1)
            post_id = match.group(2)
            return {
                'post_id': post_id,
                'blog_id': blog_id,
                'source': 'html_control_frame'
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
                return {
                    'post_id': post_url_id,
                    'blog_name': blog_name,
                    'source': 'html_post_url'
                }
                
    except Exception as e:
        print(f"从HTML中提取ID时出错: {e}")
        
    return None


def extract_blog_id_from_name(blog_name, client):
    """
    根据博客名称获取博客ID
    
    Args:
        blog_name (str): 博客名称
        client: LofterClient实例
        
    Returns:
        str: 博客ID，如果无法获取则返回None
    """
    try:
        # 使用API获取博客信息
        API_BASE_URL = "https://api.lofter.com"
        url = f"{API_BASE_URL}/v1.1/bloginfo.api"
        
        params = {
            "product": "lofter-android-7.9.7.2",
            "blogdomains": f"{blog_name}.lofter.com"
        }
        
        response = client._make_request("GET", url, params=params)
        
        # 检查响应结构
        if response and "response" in response and response["response"] is not None:
            if ("blogs" in response["response"] and 
                len(response["response"]["blogs"]) > 0):
                blog_info = response["response"]["blogs"][0]
                return str(blog_info.get("id"))
        else:
            # 如果获取失败，尝试通过其他方式获取博客信息
            print(f"无法获取博客 '{blog_name}' 的信息，可能博客已注销或设置为仅自己可见")
            
    except Exception as e:
        print(f"获取博客ID时出错: {e}")
        
    return None