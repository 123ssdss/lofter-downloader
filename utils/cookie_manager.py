import json
import os
from typing import Dict, Any


def load_cookies(cookie_file: str = 'cookie.json') -> Dict[str, Any]:
    """加载cookies配置文件"""
    if not os.path.exists(cookie_file):
        # 如果文件不存在，创建一个默认的cookie配置
        return {
            "cookies": {
                "Authorization": "",
                "LOFTER-PHONE-LOGIN-AUTH": "",
                "LOFTER_SESS": "",
                "NTES_SESS": ""
            },
            "selected_cookie_type": "LOFTER-PHONE-LOGIN-AUTH"
        }
    
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # 如果文件损坏，返回默认配置
        return {
            "cookies": {
                "Authorization": "",
                "LOFTER-PHONE-LOGIN-AUTH": "",
                "LOFTER_SESS": "",
                "NTES_SESS": ""
            },
            "selected_cookie_type": "LOFTER-PHONE-LOGIN-AUTH"
        }


def save_cookies(cookies_data: Dict[str, Any], cookie_file: str = 'cookie.json'):
    """保存cookies配置文件"""
    with open(cookie_file, 'w', encoding='utf-8') as f:
        json.dump(cookies_data, f, ensure_ascii=False, indent=4)


def update_cookie(cookie_type: str, cookie_value: str, cookie_file: str = 'cookie.json'):
    """更新指定类型的cookie值"""
    cookies_data = load_cookies(cookie_file)
    if 'cookies' not in cookies_data:
        cookies_data['cookies'] = {}
    
    cookies_data['cookies'][cookie_type] = cookie_value
    save_cookies(cookies_data, cookie_file)


def get_cookie_value(cookie_type: str, cookie_file: str = 'cookie.json') -> str:
    """获取指定类型的cookie值"""
    cookies_data = load_cookies(cookie_file)
    return cookies_data.get('cookies', {}).get(cookie_type, '')


def set_selected_cookie_type(cookie_type: str, cookie_file: str = 'cookie.json'):
    """设置当前选中的cookie类型"""
    cookies_data = load_cookies(cookie_file)
    cookies_data['selected_cookie_type'] = cookie_type
    save_cookies(cookies_data, cookie_file)


def get_selected_cookie_type(cookie_file: str = 'cookie.json') -> str:
    """获取当前选中的cookie类型"""
    cookies_data = load_cookies(cookie_file)
    return cookies_data.get('selected_cookie_type', 'LOFTER-PHONE-LOGIN-AUTH')


def interactive_cookie_setup():
    """交互式设置cookie的函数"""
    print("=== Lofter Cookie 设置向导 ===")
    
    cookies_data = load_cookies()
    
    print("\n当前已有的 cookies:")
    for cookie_type, cookie_value in cookies_data.get('cookies', {}).items():
        if cookie_value:
            print(f"  {cookie_type}: {cookie_value[:20]}... (已设置)")
        else:
            print(f"  {cookie_type}: (未设置)")
    
    print(f"\n当前选中的Cookie类型: {cookies_data.get('selected_cookie_type', 'LOFTER-PHONE-LOGIN-AUTH')}")
    
    while True:
        print("\n请选择操作:")
        print("1. 设置新的Cookie值")
        print("2. 更改当前选中的Cookie类型")
        print("3. 查看所有Cookie")
        print("4. 保存并退出")
        
        choice = input("\n请输入选项 (1-4): ").strip()
        
        if choice == '1':
            print("\n可用的Cookie类型:")
            print("1. LOFTER-PHONE-LOGIN-AUTH")
            print("2. NTES_SESS")
            print("3. Authorization")
            print("4. LOFTER_SESS")
            print("5. 自定义类型")
            
            type_choice = input("请选择Cookie类型 (1-5): ").strip()
            
            cookie_type_map = {
                '1': 'LOFTER-PHONE-LOGIN-AUTH',
                '2': 'NTES_SESS',
                '3': 'Authorization',
                '4': 'LOFTER_SESS'
            }
            
            if type_choice in cookie_type_map:
                cookie_type = cookie_type_map[type_choice]
            elif type_choice == '5':
                cookie_type = input("请输入自定义Cookie类型: ").strip()
            else:
                print("无效选择，跳过...")
                continue
            
            cookie_value = input(f"请输入{cookie_type}的值: ").strip()
            update_cookie(cookie_type, cookie_value)
            print(f"已设置 {cookie_type} = {cookie_value[:20]}...")
        
        elif choice == '2':
            print("\n可用的Cookie类型:")
            for i, cookie_type in enumerate(cookies_data.get('cookies', {}).keys(), 1):
                print(f"{i}. {cookie_type}")
            
            type_choice = input("请选择要使用的Cookie类型编号: ").strip()
            cookie_types = list(cookies_data.get('cookies', {}).keys())
            
            try:
                idx = int(type_choice) - 1
                if 0 <= idx < len(cookie_types):
                    selected_type = cookie_types[idx]
                    set_selected_cookie_type(selected_type)
                    print(f"已选择Cookie类型: {selected_type}")
                else:
                    print("无效选择")
            except ValueError:
                print("请输入有效数字")
        
        elif choice == '3':
            print("\n所有Cookie值:")
            for cookie_type, cookie_value in cookies_data.get('cookies', {}).items():
                if cookie_value:
                    print(f"  {cookie_type}: {cookie_value}")
                else:
                    print(f"  {cookie_type}: (未设置)")
        
        elif choice == '4':
            save_cookies(cookies_data)
            print("Cookie配置已保存到 cookie.json")
            break
        
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    interactive_cookie_setup()