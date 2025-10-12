import time
import json
import os
from network import LofterClient
from utils.path_manager import path_manager
from config import BETWEEN_BATCHES_DELAY


def process_subscription(client, download_comments, browser='default'):
    """Processes subscription list from the user's subscriptions."""
    
    # 直接调用LofterClient中的方法，该方法内部会处理认证信息
    # 这样可以确保认证信息的获取和验证完全在LofterClient中完成
    # 传入None，让get_subs方法内部处理认证信息获取
    client.save_subscription_list(auth_info=None, save_path='./results')

    print("订阅列表获取完成！")
