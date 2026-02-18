"""
Lofter - LofterID 登录独立脚本
接口：POST https://www.lofter.com/lpt/account/login.do
"""

import hashlib
import json
import sys
import requests

# ── 常量 ──────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.lofter.com"
LOGIN_ENDPOINT = "/lpt/account/login.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.lofter.com/front/login",
    "Origin": "https://www.lofter.com",
}


# ── 加密工具 ──────────────────────────────────────────────────────────────────
def calculate_sha256(text: str) -> str:
    """
    对字符串进行 SHA-256 哈希，返回小写十六进制字符串。
    对应 Dart: calculateSHA256(String input)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 登录函数 ──────────────────────────────────────────────────────────────────
def login_by_lofter_id(
    lofter_id: str,
    password: str,
    session: requests.Session | None = None,
    timeout: int = 15,
) -> dict:
    """
    使用 LofterID（博客名）和密码登录 Lofter。

    对应 Dart:
        static Future<dynamic> loginByLofterID(
            String lofterID, String password) async {
          return RequestUtil.post(
            "/lpt/account/login.do",
            domainType: DomainType.www,
            data: {
              "blogName": lofterID,
              "password": calculateSHA256(password),
            },
          );
        }

    Args:
        lofter_id: 用户博客名（LofterID），如 "username"
        password:  用户明文密码，脚本内部会自动 SHA-256 哈希
        session:   可选，复用已有 requests.Session（携带 Cookie 等）
        timeout:   请求超时秒数，默认 15

    Returns:
        dict，包含以下字段：
            success  (bool)  – 是否登录成功
            code     (int)   – HTTP 状态码
            data     (any)   – 服务端返回的 JSON 数据（或原始文本）
            error    (str)   – 若发生异常，错误信息
    """
    hashed_password = calculate_sha256(password)

    payload = {
        "blogName": lofter_id,
        "password": hashed_password,
    }

    print(f"[*] 登录账号   : {lofter_id}")
    print(f"[*] 密码哈希   : {hashed_password}")
    print(f"[*] 请求地址   : {BASE_URL}{LOGIN_ENDPOINT}")

    client = session or requests.Session()

    try:
        resp = client.post(
            url=BASE_URL + LOGIN_ENDPOINT,
            data=payload,          # application/x-www-form-urlencoded
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )

        print(f"[*] HTTP 状态码: {resp.status_code}")

        # 尝试解析 JSON
        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        success = resp.status_code == 200 and (
            isinstance(body, dict) and body.get("code") in (200, 0, None)
        )

        return {
            "success": success,
            "code": resp.status_code,
            "data": body,
            "error": None,
        }

    except requests.exceptions.ConnectionError as e:
        return {"success": False, "code": -1, "data": None, "error": f"连接失败: {e}"}
    except requests.exceptions.Timeout:
        return {"success": False, "code": -1, "data": None, "error": "请求超时"}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "code": -1, "data": None, "error": str(e)}


# ── 主程序入口 ─────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 55)
    print("  Lofter LofterID 登录脚本")
    print("=" * 55)

    # 支持命令行参数：python lofter_login_by_id.py <lofterID> <password>
    if len(sys.argv) == 3:
        lofter_id = sys.argv[1]
        password = sys.argv[2]
    else:
        lofter_id = input("请输入 LofterID（博客名）: ").strip()
        password = input("请输入密码            : ").strip()

    if not lofter_id or not password:
        print("[!] LofterID 和密码不能为空，退出。")
        sys.exit(1)

    result = login_by_lofter_id(lofter_id, password)

    print("\n── 响应结果 " + "─" * 43)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["success"]:
        print("\n[✓] 登录成功！")
    else:
        print(f"\n[✗] 登录失败：{result.get('error') or result.get('data')}")


if __name__ == "__main__":
    main()
