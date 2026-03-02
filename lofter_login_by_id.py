import hashlib
import json
import time

import requests


def sha256_encrypt(password):
    """Encrypt password using SHA-256"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login_lofter(blog_name, password):
    """
    Simple Lofter login emulator
    """
    # Prepare login data
    encrypted_password = sha256_encrypt(password)

    # Login URL with timestamp
    timestamp = str(int(time.time() * 1000))
    url = f"https://www.lofter.com/lpt/account/login.do?product=lofter-pc&_={timestamp}"

    # Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://www.lofter.com",
        "Referer": "https://www.lofter.com/front/login/",
        "Accept": "*/*",
    }

    # Login data
    data = {"blogName": blog_name, "password": encrypted_password}

    # Create session and get initial cookies
    session = requests.Session()
    session.get("https://www.lofter.com/front/login/")

    # Send login request
    response = session.post(url, headers=headers, data=data)

    # Return JSON response
    return response.json()


# Example usage
if __name__ == "__main__":
    # Get user input for credentials
    blog_name = input("请输入Lofter博客名称: ")
    password = input("请输入密码: ")

    try:
        result = login_lofter(blog_name, password)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
