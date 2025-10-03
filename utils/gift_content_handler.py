"""Lofter付费彩蛋内容处理

该模块提供处理Lofter付费彩蛋内容的功能，包括解析API响应中的
showGift和returnContent字段，以及合并付费内容与普通内容。
"""

import json
from typing import Optional, Dict, Any, List


def resolve_article(json_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """解析文章内容，包括付费彩蛋内容
    
    Args:
        json_info: 包含帖子信息的字典
        
    Returns:
        合并后的文章内容，如果解析失败则返回None
    """
    try:
        if isinstance(json_info, dict):
            content = json_info['response']['posts'][0]['post']['content'].strip()
            return_content_data = json_info['response']['posts'][0]['post'].get('returnContent', [None])[0]
            
            if return_content_data:
                return_content = return_content_data.get('content', None)
                if return_content:
                    gift_content_html = (
                        '<h3>以下为彩蛋内容</h3>\n'
                        '<p id="GiftContent" style="white-space: pre-line;">'
                        f'{return_content}</p>'
                    )
                    return content + '\n' + gift_content_html
            return content
        else:
            return None

    except KeyError as e:
        print(f"解析JSON时发生错误: {e}")
        return None


def resolve_picture(content: Optional[Dict[str, Any]]) -> str:
    """解析图片内容，包括付费彩蛋图片
    
    Args:
        content: 包含帖子信息的字典
        
    Returns:
        包含所有图片链接的JSON字符串
        
    Raises:
        ValueError: 当内容为空或缺少必要字段时
    """
    if content is None:
        raise ValueError("内容为空，无法解析图片URL")
    
    try:
        # 解析普通图片链接
        url_all: List = list(json.loads(content['response']['posts'][0]['post']['photoLinks']))
        
        # 获取付费彩蛋图片链接
        return_content = content['response']['posts'][0]['post'].get('returnContent', None)
        
        if return_content:
            return_img_all = return_content[0].get('images', [])
            for img in return_img_all:
                url_all.append(img)
        
        # 确保JSON格式正确
        return str(url_all).replace("'", '"').replace('True', 'true').replace('False', 'false')
    
    except KeyError:
        raise ValueError("无法解析图片URL，缺少必要的字段")


def check_gift_status(content: Optional[Dict[str, Any]]) -> Optional[int]:
    """检查帖子是否包含付费内容
    
    Args:
        content: 包含帖子信息的字典
        
    Returns:
        0-不需要付费，1-需要付费，None-无法确定
    """
    if content is None:
        raise ValueError("内容为空，无法解析付费信息")
    
    try:
        return int(content['response']['posts'][0]['post']['showGift'])
    except KeyError:
        raise ValueError("无法解析付费信息，缺少必要的字段")
    except (TypeError, ValueError):
        return None


def has_gift_content(content: Optional[Dict[str, Any]]) -> bool:
    """检查帖子是否包含付费彩蛋内容
    
    Args:
        content: 包含帖子信息的字典
        
    Returns:
        True-包含付费彩蛋内容，False-不包含
    """
    if content is None:
        return False
    
    try:
        show_gift = content['response']['posts'][0]['post'].get('showGift', False)
        return_content = content['response']['posts'][0]['post'].get('returnContent', [])
        
        return bool(show_gift) and bool(return_content)
    except KeyError:
        return False