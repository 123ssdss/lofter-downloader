import os
from typing import Optional
from config import OUTPUT_DIR, JSON_DIR


class PathManager:
    """路径管理器，用于处理所有文件存储路径"""
    
    def __init__(self):
        self.base_output_dir = OUTPUT_DIR
        self.base_json_dir = JSON_DIR
        
        # 创建基础目录
        os.makedirs(self.base_output_dir, exist_ok=True)
        os.makedirs(self.base_json_dir, exist_ok=True)
    
    def get_output_dir(self, mode: str, name: str) -> str:
        """
        获取输出目录路径
        
        Args:
            mode: 模式类型 ('tag', 'collection', 'blog', 'comment', 'subscription')
            name: 具体名称 (tag名称、collection名称等)
        """
        if mode not in ['tag', 'collection', 'blog', 'comment', 'subscription']:
            raise ValueError(f"Invalid mode: {mode}. Must be one of 'tag', 'collection', 'blog', 'comment', 'subscription'")
        
        output_dir = os.path.join(self.base_output_dir, mode, name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def get_json_dir(self, mode: str, name: str, sub_dir: Optional[str] = None) -> str:
        """
        获取JSON存储目录路径
        
        Args:
            mode: 模式类型 ('tag', 'collection', 'blog', 'comment', 'subscription')
            name: 具体名称 (tag名称、collection名称等)
            sub_dir: 子目录名称 (如 'comments', 'blog' 等)
        """
        if mode not in ['tag', 'collection', 'blog', 'comment', 'subscription']:
            raise ValueError(f"Invalid mode: {mode}. Must be one of 'tag', 'collection', 'blog', 'comment', 'subscription'")
        
        if sub_dir:
            json_dir = os.path.join(self.base_json_dir, mode, name, sub_dir)
        else:
            json_dir = os.path.join(self.base_json_dir, mode, name)
        
        os.makedirs(json_dir, exist_ok=True)
        return json_dir
    
    def get_photo_dir(self, mode: str, name: str) -> str:
        """
        获取图片存储目录路径
        
        Args:
            mode: 模式类型 ('tag', 'collection', 'blog', 'comment', 'subscription')
            name: 具体名称 (tag名称、collection名称等)
        """
        if mode not in ['tag', 'collection', 'blog', 'comment', 'subscription']:
            raise ValueError(f"Invalid mode: {mode}. Must be one of 'tag', 'collection', 'blog', 'comment', 'subscription'")
        
        photo_dir = os.path.join("photo", mode, name)
        os.makedirs(photo_dir, exist_ok=True)
        return photo_dir


# 全局路径管理器实例
path_manager = PathManager()