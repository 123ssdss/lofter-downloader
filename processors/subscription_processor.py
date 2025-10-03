import time
import json
import os
import requests
from network import LofterClient
from utils.path_manager import path_manager
from config import BETWEEN_BATCHES_DELAY


def get_subs(auth_info, offset=0, limit_once=50):
    # 获取订阅列表，需要登录信息(LOFTER-PHONE-LOGIN-AUTH和NTES_SESS)
    url = "https://api.lofter.com/newapi/subscribeCollection/list.json"
    params = {
    'offset': offset,
    'limit': limit_once
    }

    headers = {
    'User-Agent': "LOFTER-Android 7.6.12 (V2272A; Android 13; null) WIFI",
    'Accept-Encoding': "br,gzip",
    'lofter-phone-login-auth': auth_info['LOFTER-PHONE-LOGIN-AUTH'],
    }
    
    # Add Cookie header if either authkey or NTES_SESS is provided
    authkey = auth_info.get('LOFTER-PHONE-LOGIN-AUTH', '')
    ntes_sess = auth_info.get('NTES_SESS', '')
    
    if authkey or ntes_sess:
        cookie_parts = []
        if authkey:
            cookie_parts.append(f"LOFTER-PHONE-LOGIN-AUTH={authkey}")
        if ntes_sess:
            cookie_parts.append(f"NTES_SESS={ntes_sess}")
        headers['Cookie'] = "; ".join(cookie_parts)

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        result = json.loads(response.text)
        return result
    else:
        return None


def save_subs(auth_info, save_path='./results', sleep_time=BETWEEN_BATCHES_DELAY, limit_once=50):
    '''
    保存订阅列表到 txt 文件和 json 文件

    Args:
    auth_info: 登录信息字典，包含LOFTER-PHONE-LOGIN-AUTH和NTES_SESS
    save_path: 保存路径，默认为'./results'
    sleep_time: 请求间隔，默认为0.1秒
    limit_once: 次获取数量，默认为50
    '''

    # 为订阅模式使用专门的路径，实现隔离
    # 使用空字符串作为 name 参数，将直接创建在 output/subscription 下
    output_dir = path_manager.get_output_dir('subscription', '')
    json_dir = path_manager.get_json_dir('subscription', 'subscription')
    
    os.makedirs(save_path, exist_ok=True)  # 确保 ./results 目录存在
    
    start = 0 # 起始位置
    response = get_subs(auth_info, start)
    if not response:
        print("获取订阅列表失败")
        return
    data = response['data']
    offset = data['offset'] # 结束位置
    subscribeCollectionCount = data['subscribeCollectionCount']
    collections = data['collections']

    if subscribeCollectionCount > limit_once:
        for i in range(limit_once, subscribeCollectionCount, limit_once):
            time.sleep(sleep_time)
            response = get_subs(auth_info, i, limit_once)
            if response:
                data = response['data']
                collections += data['collections']

    # 写入txt文件
    # 直接在 output 目录下创建 subscription.txt 文件
    txt_file_path = os.path.join('output', 'subscription.txt')
    os.makedirs('output', exist_ok=True)
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(f"订阅总数: {subscribeCollectionCount}\n")
        f.write("="*50 + "\n")
        for c in collections:
            collection_id = c['collectionId']
            if not c.get('valid', True):  # 如果没有valid字段，默认为True
                print(f'合集{collection_id}已失效')
                continue
            collection_name = c['name']
            f.write(f'合集名：{collection_name}\n')
            f.write(f'合集ID：{collection_id}\n')
            
            # 只有当值存在且不为空时才写入
            author_name = c.get('blogInfo', {}).get('blogNickName', '')
            if author_name:
                f.write(f'作者：{author_name}\n')
            collection_url = c.get('collectionUrl', '')
            if collection_url:
                f.write(f'链接：{collection_url}\n')
            f.write("-" * 30 + "\n")
            print(f'合集名：{collection_name}，合集ID：{collection_id}')

    print(f'订阅信息保存至 {txt_file_path}')
    
    # 保存为JSON文件到 ./results/subscription.json (用户期望的路径)
    json_file_path = os.path.join(save_path, 'subscription.json')
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(collections, f, ensure_ascii=False, indent=2)
    print(f'订阅信息保存至 {json_file_path}')
    
    # 保存到用户要求的路径：./json/subscription.json
    user_json_path = os.path.join('json', 'subscription.json')
    os.makedirs('json', exist_ok=True)
    with open(user_json_path, 'w', encoding='utf-8') as f:
        json.dump(collections, f, ensure_ascii=False, indent=2)
    print(f'订阅信息JSON保存至 {user_json_path}')


def process_subscription(client, download_comments, authkey='', ntes_sess='', browser='default'):
    """Processes subscription list from the user's subscriptions."""
    
    # 优先使用传入的authkey参数，否则使用client对象中的认证信息
    auth_info = {
        'LOFTER-PHONE-LOGIN-AUTH': authkey or client.auth_key or '',
        'NTES_SESS': ntes_sess or client.ntes_sess or ''
    }
    
    if authkey or client.auth_key:
        print(f"使用提供的authkey进行认证")
    else:
        print("使用 cookies.json 中的认证信息进行认证")
    
    # 保存订阅信息 - 这是主要功能，与示例项目中的subscription.py一致
    save_subs(auth_info, save_path='./results')  # 使用默认参数
    
    print("订阅列表获取完成！")

