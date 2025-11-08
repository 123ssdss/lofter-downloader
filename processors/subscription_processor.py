"""
订阅处理器
专门处理LOFTER订阅列表的获取和保存
"""
import json
import os
from typing import Dict, Any, List
from processors.base_processor import BaseProcessor
from config import BETWEEN_BATCHES_DELAY


class SubscriptionProcessor(BaseProcessor):
    """订阅处理器"""
    
    def __init__(self, client, debug: bool = False):
        super().__init__(client, debug)
    
    def fetch_subscription_list(self) -> List[Dict[str, Any]]:
        """获取订阅列表"""
        try:
            # 使用fetch_subscription_collections方法获取所有订阅，而不是只获取一页
            subscription_data = self.client.fetch_subscription_collections()
            
            if not subscription_data:
                self.logger.warning("没有获取到订阅数据")
                return []
            
            self.logger.info(f"获取到 {len(subscription_data)} 个订阅")
            return subscription_data
            
        except Exception as e:
            self.handle_error(e, "获取订阅列表")
            return []
    
    def save_subscription_list(self, subscription_data: List[Dict[str, Any]], save_path: str = './results') -> str:
        """保存订阅列表到文件"""
        try:
            # 确保目录存在
            os.makedirs(save_path, exist_ok=True)
            
            # 保存到文件
            file_path = os.path.join(save_path, 'subscription.json')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(subscription_data, f, ensure_ascii=False, indent=4)
            
            self.logger.info(f"订阅列表已保存到: {file_path}")
            return file_path
            
        except Exception as e:
            self.handle_error(e, f"保存订阅列表到 {save_path}")
            return ""
    
    def format_subscription_info(self, subscription_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """格式化订阅信息"""
        try:
            total_subscriptions = len(subscription_data)
            unread_count = sum(sub.get('unreadCount', 0) for sub in subscription_data)
            
            # 统计合集类型
            collection_types = {}
            for sub in subscription_data:
                collection_type = sub.get('collectionType', 'unknown')
                collection_types[collection_type] = collection_types.get(collection_type, 0) + 1
            
            # 获取最新的订阅
            recent_subscriptions = sorted(
                subscription_data, 
                key=lambda x: x.get('recentlyRead', 0), 
                reverse=True
            )[:5]
            
            return {
                "total_subscriptions": total_subscriptions,
                "total_unread": unread_count,
                "collection_types": collection_types,
                "recent_subscriptions": recent_subscriptions,
                "subscriptions": subscription_data
            }
            
        except Exception as e:
            self.handle_error(e, "格式化订阅信息")
            return {"subscriptions": subscription_data}
    
    def process(self, save_path: str = './results') -> Dict[str, Any]:
        """处理订阅列表的主要接口"""
        try:
            self.logger.info("开始获取订阅列表...")
            
            # 获取订阅数据
            subscription_data = self.fetch_subscription_list()
            
            if not subscription_data:
                return {
                    "success": False,
                    "message": "没有获取到订阅数据或订阅列表为空"
                }
            
            # 保存订阅数据
            file_path = self.save_subscription_list(subscription_data, save_path)
            
            # 格式化订阅信息
            formatted_info = self.format_subscription_info(subscription_data)
            
            # 添加延迟
            import time
            time.sleep(BETWEEN_BATCHES_DELAY)
            
            result = {
                "success": True,
                "file_path": file_path,
                "total_subscriptions": formatted_info.get("total_subscriptions", 0),
                "total_unread": formatted_info.get("total_unread", 0),
                "message": "订阅列表获取完成！"
            }
            
            self.logger.info(f"订阅列表处理完成: {result['total_subscriptions']} 个订阅")
            
            return result
            
        except Exception as e:
            self.handle_error(e, "处理订阅列表")
            return {"success": False, "error": str(e)}