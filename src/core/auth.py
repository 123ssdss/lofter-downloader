"""
src/core/auth.py
Lofter 登录认证 — 支持通过 LofterID + 密码登录，获取 Authorization token。
整合自原始项目的 lofter_login_by_id.py。
"""
import hashlib
import json
from typing import Optional

import requests

_BASE_URL       = "https://www.lofter.com"
_LOGIN_ENDPOINT = "/lpt/account/login.do"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.lofter.com/front/login",
    "Origin":  "https://www.lofter.com",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def login_by_lofter_id(
    lofter_id: str,
    password: str,
    session: Optional[requests.Session] = None,
    timeout: int = 15,
) -> dict:
    """
    使用 LofterID（博客名）和密码登录 Lofter。
    密码在发送前自动做 SHA-256 哈希处理。

    Returns:
        {
          "success": bool,
          "code":    int,       # HTTP 状态码
          "data":    any,       # 服务端返回 JSON 或原始文本
          "cookie":  str|None,  # 登录成功时的 Authorization 值
          "error":   str|None,
        }
    """
    hashed = _sha256(password)
    payload = {"blogName": lofter_id, "password": hashed}
    client  = session or requests.Session()

    try:
        resp = client.post(
            _BASE_URL + _LOGIN_ENDPOINT,
            data=payload,
            headers=_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        success = resp.status_code == 200 and (
            isinstance(body, dict) and body.get("code") in (200, 0, None)
        )

        # 尝试从 Set-Cookie 或响应体中提取 Authorization token
        auth_value: Optional[str] = None
        if success:
            set_cookie = resp.headers.get("Set-Cookie", "")
            for part in set_cookie.split(";"):
                part = part.strip()
                if part.startswith("Authorization="):
                    auth_value = part[len("Authorization="):]
                    break
            # 有些版本直接在 body 里返回 token
            if not auth_value and isinstance(body, dict):
                auth_value = (
                    body.get("Authorization")
                    or body.get("token")
                    or body.get("authToken")
                )

        return {
            "success": success,
            "code":    resp.status_code,
            "data":    body,
            "cookie":  auth_value,
            "error":   None,
        }

    except requests.exceptions.ConnectionError as e:
        return {"success": False, "code": -1, "data": None,
                "cookie": None, "error": f"连接失败: {e}"}
    except requests.exceptions.Timeout:
        return {"success": False, "code": -1, "data": None,
                "cookie": None, "error": "请求超时"}
    except Exception as e:
        return {"success": False, "code": -1, "data": None,
                "cookie": None, "error": str(e)}
