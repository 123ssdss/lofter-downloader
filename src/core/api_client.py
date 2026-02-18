"""
src/core/api_client.py
Lofter API 客户端 — 纯网络请求层，不做任何文件 I/O。
所有与 Lofter 服务器的通信都经由此类。
"""
import concurrent.futures
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

import config
from cookie import USER_COOKIE

# ── API 端点 ──────────────────────────────────────────────────
_BASE           = "https://api.lofter.com"
TAG_POSTS_URL   = f"{_BASE}/newapi/tagPosts.json"
POST_DETAIL_URL = f"{_BASE}/oldapi/post/detail.api"
L1_COMMENTS_URL = f"{_BASE}/comment/l1/page.json"
L2_COMMENTS_URL = f"{_BASE}/comment/l2/page/abtest.json"
COLLECTION_URL  = f"{_BASE}/v1.1/postCollection.api"
SUBSCRIPTION_URL= f"{_BASE}/newapi/subscribeCollection/list.json"
BLOGINFO_URL    = f"{_BASE}/v1.1/bloginfo.api"


# ── 固定请求头（模拟 Android 客户端，不含 Cookie）──────────────
# Cookie 在每次请求时动态从 cookie.py 读取，避免模块缓存问题
_BASE_HEADERS = {
    "user-agent":      "LOFTER-Android 8.0.12 (LM-V409N; Android 15; null) WIFI",
    "market":          "LGE",
    "androidid":       "3451efd56bgg6h47",
    "accept-encoding": "gzip",
    "x-device":        "qv+Dz73SObtbEFG7P0Gq12HkjzNb+iOK6KHWTPKHBTEZu26C6MJOMukkAG7dETo2",
    "x-reqid":         "0H62K0V7",
    "content-type":    "application/x-www-form-urlencoded",
    "dadeviceid":      "2ef9ea6c17b7c6881c71915a4fefd932edc01af0",
    "lofproduct":      "lofter-android-8.0.12",
    "host":            "api.lofter.com",
    "portrait": (
        "eyJpbWVpIjoiMzQ1MWVmZDU2YmdnNmg0NyIsImFuZHJvaWRJZCI6IjM0NTFlZmQ1NmJnZzZoNDci"
        "LCJvYWlkIjoiMzJiNGQyYzM0ODY1MDg0MiIsIm1hYyI6IjAyOjAwOjAwOjAwOjAwOjAwIiwicGhv"
        "bmUiOiIxNTkzNDg2NzI5MyJ9"
    ),
}


class LofterClient:
    """
    Lofter API 客户端。
    只负责发送 HTTP 请求并返回解析后的 JSON；
    不做任何文件写入或业务逻辑处理。
    """

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug

        # ── 每次实例化时重新从 cookie.py 读取 Cookie ──────────────
        # 直接导入当前运行时的 USER_COOKIE（不依赖模块级常量）
        import importlib, sys
        if "cookie" in sys.modules:
            _ck_mod = importlib.reload(sys.modules["cookie"])
        else:
            import cookie as _ck_mod  # type: ignore
        _ck = _ck_mod.USER_COOKIE
        _raw = f"{_ck['name']}={_ck['value']}"
        try:
            _raw.encode("latin-1")
            _cookie_str = _raw
        except UnicodeEncodeError:
            _cookie_str = _raw.encode("ascii", errors="ignore").decode("ascii")
            if not _cookie_str.strip():
                print(
                    "\033[31m[ERR]\033[0m  cookie.py 的 value 包含非 ASCII 字符，"
                    "请替换为真实的 Lofter Authorization token。"
                )

        self._headers = _BASE_HEADERS.copy()
        self._headers["Cookie"] = _cookie_str

        if debug:
            print(f"\033[37m[DEBUG][LofterClient]\033[0m Cookie: "
                  f"{_cookie_str[:30]}…（共 {len(_cookie_str)} 字节）")

        self.session = requests.Session()
        self.session.headers.update(self._headers)

    # ── 内部工具 ────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self.debug:
            safe = str(msg).encode("utf-8", "replace").decode("utf-8")
            print(f"\033[37m[DEBUG][LofterClient]\033[0m {safe}")

    def _request(self, method: str, url: str, *,
                 params: dict = None, data=None,
                 headers: dict = None,
                 max_retries: int = None) -> Optional[dict]:
        """通用请求方法，含重试逻辑。返回解析后的 JSON dict 或 None。"""
        retries = max_retries if max_retries is not None else config.MAX_RETRIES
        hdrs    = self._headers.copy()   # 使用实例级 headers（含最新 Cookie）
        if headers:
            hdrs.update(headers)

        # Debug: 打印实际发出的请求头（Cookie 脱敏显示最后8位）
        if self.debug:
            safe_hdrs = {}
            for k, v in hdrs.items():
                if k.lower() == "cookie":
                    safe_hdrs[k] = v[:20] + "…" + v[-8:] if len(v) > 28 else v
                else:
                    safe_hdrs[k] = v
            self._log(f"→ {method.upper()} {url}")
            if params:
                self._log(f"  params : {params}")
            if data:
                self._log(f"  data   : {str(data)[:200]}")
            self._log(f"  headers: {safe_hdrs}")

        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, headers=hdrs,
                                            timeout=config.REQUEST_TIMEOUT)
                else:
                    resp = self.session.post(url, data=data, headers=hdrs,
                                             timeout=config.REQUEST_TIMEOUT)

                resp.raise_for_status()
                result = resp.json()

                if isinstance(result, dict) and result.get("code") == 500:
                    self._log(f"API error (attempt {attempt+1}/{retries}): {result.get('msg')}")
                    if attempt < retries - 1:
                        time.sleep(3 + 2 ** attempt)
                        continue
                    return None

                return result

            except (requests.RequestException, json.JSONDecodeError) as e:
                self._log(f"Request failed (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(3 + 2 ** attempt)

        return None

    # ── 标签 API ────────────────────────────────────────────────

    def fetch_posts_by_tag(
        self,
        tag: str,
        list_type: str  = None,
        timelimit: str  = None,
        blog_type: str  = None,
    ) -> List[dict]:
        """获取某标签下的所有帖子元数据列表（自动翻页）。"""
        list_type = list_type or config.DEFAULT_LIST_TYPE
        timelimit = timelimit if timelimit is not None else config.DEFAULT_TIME_LIMIT
        blog_type = blog_type or config.DEFAULT_BLOG_TYPE

        all_posts:   List[dict] = []
        all_pages:   List[dict] = []   # 原始分页响应，供调用者存档
        permalinks:  set        = set()
        offset:      int        = 0

        print(f"\033[32m[INFO]\033[0m 开始获取标签 '{tag}' 的帖子…")

        while True:
            data = {
                "postTypes": blog_type,
                "offset":    str(offset),
                "postYm":    timelimit,
                "tag":       tag,
                "type":      list_type,
                "limit":     10,
            }
            resp = self._request("POST", TAG_POSTS_URL, data=data)
            if resp:
                all_pages.append(resp)

            if not resp or "data" not in resp or not resp["data"].get("list"):
                break

            posts = resp["data"]["list"]
            if not posts:
                break

            first_permalink = posts[0]["postData"]["postView"]["permalink"]
            if first_permalink in permalinks:
                break

            new_posts = [p for p in posts
                         if p["postData"]["postView"]["permalink"] not in permalinks]
            all_posts.extend(new_posts)
            for p in new_posts:
                permalinks.add(p["postData"]["postView"]["permalink"])

            offset = resp["data"]["offset"]
            print(f"\033[32m[INFO]\033[0m 标签 '{tag}': 已获取 {len(all_posts)} 篇")
            time.sleep(config.BETWEEN_PAGES_DELAY)

        print(f"\033[32m[INFO]\033[0m 标签 '{tag}' 获取完成，共 {len(all_posts)} 篇")
        # 把原始分页数据也挂在返回值上，供 TagService 存档
        self._last_tag_pages = all_pages
        return all_posts

    # ── 帖子详情 API ────────────────────────────────────────────

    def fetch_post_detail(self, post_meta: dict) -> Optional[dict]:
        """通过 post_meta 字典获取帖子详情。"""
        blog_info = post_meta["blogInfo"]
        post_view = post_meta["postData"]["postView"]
        data = {
            "targetblogid": blog_info["blogId"],
            "blogdomain":   f"{blog_info['blogName']}.lofter.com",
            "postid":       str(post_view["id"]),
            "product":      "lofter-android-7.9.7.2",
        }
        return self._request("POST", POST_DETAIL_URL, data=data)

    def fetch_post_detail_by_id(self, post_id: str, blog_id: str) -> Optional[dict]:
        """通过 post_id + blog_id 直接获取帖子详情（自动解析博客域名）。"""
        # 先尝试获取博客域名
        blog_resp = self._request("GET", BLOGINFO_URL,
                                  params={"product": "lofter-android-7.9.7.2",
                                          "blogids": str(blog_id)})
        blog_domain = f"{blog_id}.lofter.com"
        if (blog_resp
                and "response" in blog_resp
                and blog_resp["response"]               # ← 防止 response 为 None
                and blog_resp["response"].get("blogs")):
            blog_name = blog_resp["response"]["blogs"][0].get("blogname")
            if blog_name:
                blog_domain = f"{blog_name}.lofter.com"

        data = {
            "targetblogid": str(blog_id),
            "blogdomain":   blog_domain,
            "postid":       str(post_id),
            "product":      "lofter-android-7.9.7.2",
        }
        return self._request("POST", POST_DETAIL_URL, data=data)

    # ── 评论 API ────────────────────────────────────────────────

    def fetch_all_comments(
        self,
        post_id: str,
        blog_id: str,
        max_retries: int = 3,
    ) -> dict:
        """
        获取帖子的全部评论（L1 + L2 回复）。
        返回 {"hot_list": [...], "all_list": [...]}，每条评论已归一化。
        """
        for attempt in range(max_retries):
            try:
                return self._fetch_all_comments_once(post_id, blog_id)
            except Exception as e:
                self._log(f"评论获取失败 (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
        return {"hot_list": [], "all_list": []}

    def _fetch_all_comments_once(self, post_id: str, blog_id: str) -> dict:
        offset          = 0
        hot_comments:   List[dict] = []
        all_comments:   List[dict] = []
        seen_ids:       set        = set()
        page            = 1

        while True:
            params = {
                "postId":          post_id,
                "blogId":          blog_id,
                "offset":          offset,
                "product":         "lofter-android-8.2.18",
                "needGift":        0,
                "openFansVipPlan": 0,
                "dunType":         1,
            }
            resp = self._request("GET", L1_COMMENTS_URL, params=params)

            if not resp or resp.get("code") != 0 or "data" not in resp:
                break

            for c in resp["data"].get("hotList", []):
                cid = c.get("id")
                if cid and cid not in seen_ids:
                    c["is_hot_comment"] = True
                    hot_comments.append(c)
                    seen_ids.add(cid)

            for c in resp["data"].get("list", []):
                cid = c.get("id")
                if cid and cid not in seen_ids:
                    c["is_hot_comment"] = False
                    all_comments.append(c)
                    seen_ids.add(cid)

            next_offset = resp["data"].get("offset", -1)
            if next_offset == -1:
                break
            offset = next_offset
            page  += 1
            time.sleep(config.COMMENT_REQUEST_DELAY)

        combined = hot_comments + all_comments

        # 并发获取 L2 回复
        def _with_replies(c: dict) -> dict:
            return self._attach_l2_replies(post_id, blog_id, c)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.COMMENT_MAX_WORKERS
        ) as ex:
            hot_done = list(ex.map(_with_replies, hot_comments))
            all_done = list(ex.map(_with_replies, combined))

        return {"hot_list": hot_done, "all_list": all_done}

    def _attach_l2_replies(self, post_id: str, blog_id: str,
                           l1_comment: dict) -> dict:
        """给 L1 评论附加归一化后的 L2 回复列表，并返回归一化的 L1 评论。"""
        comment_id    = l1_comment["id"]
        embedded_l2   = l1_comment.get("l2Comments", [])
        l2_count      = l1_comment.get("l2Count", 0)
        normalized    = self._normalize_comment(l1_comment)
        replies       = [self._normalize_comment(r) for r in embedded_l2]

        if l2_count > len(embedded_l2):
            extra = self._fetch_l2(post_id, blog_id, comment_id)
            embedded_ids = {r.get("id") for r in embedded_l2}
            for r in extra:
                if r.get("id") not in embedded_ids:
                    replies.append(self._normalize_comment(r))

        normalized["replies"]  = replies
        normalized["l2_count"] = len(replies)
        return normalized

    def _fetch_l2(self, post_id: str, blog_id: str,
                  comment_id: str) -> List[dict]:
        """获取单条 L1 评论的 L2 回复列表（raw）。"""
        time.sleep(config.L2_COMMENT_REQUEST_DELAY)
        params = {
            "postId":  post_id,
            "blogId":  blog_id,
            "id":      comment_id,
            "offset":  0,
            "fromSrc": "",
            "fromId":  "",
        }
        resp = self._request("GET", L2_COMMENTS_URL, params=params)
        if not resp or resp.get("code") != 0:
            return []
        data = resp.get("data", {})
        return (data.get("list") or
                resp.get("list") or
                (data if isinstance(data, list) else []))

    @staticmethod
    def _normalize_comment(raw: dict) -> dict:
        """将原始评论字典转换为统一格式（与原版完全一致）。"""
        pub_info = raw.get("publisherBlogInfo", {})
        pub_ts   = raw.get("publishTime", 0)
        pub_str  = (datetime.fromtimestamp(pub_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    if pub_ts else "")
        return {
            "id":                   raw.get("id", ""),
            "content":              raw.get("content", "").strip(),
            "publishTime":          pub_ts,
            "publishTimeFormatted": pub_str,
            "likeCount":            raw.get("likeCount", 0),
            "ipLocation":           raw.get("ipLocation", ""),
            "quote":                raw.get("quote", ""),
            "author": {
                "blogNickName": pub_info.get("blogNickName", ""),
                "blogId":       pub_info.get("blogId", ""),
                "blogName":     pub_info.get("blogName", ""),
                "avatar":       pub_info.get("smallLogo", ""),
            },
            "emotes":   raw.get("emotes", []),
            "replyTo":  raw.get("replyTo", {}),
            "replies":  [],
            "l2_count": 0,
        }

    # ── 合集 API ────────────────────────────────────────────────

    def get_collection_list(self, collection_id: str,
                            offset: int = 0, limit: int = 15) -> Optional[dict]:
        """获取合集详情（含帖子列表）。"""
        payload = (
            f"method=getCollectionDetail"
            f"&offset={offset}&limit={limit}"
            f"&collectionid={collection_id}&order=1"
        )
        hdrs = self._headers.copy()
        try:
            resp = requests.post(
                COLLECTION_URL,
                params={"product": "lofter-android-7.6.12"},
                data=payload,
                headers=hdrs,
                timeout=15,
            )
            resp.raise_for_status()
            body = resp.content.decode("utf-8", errors="replace")
            data = json.loads(body)
            return data.get("response") if data else None
        except Exception as e:
            self._log(f"get_collection_list error: {e}")
            return None

    # ── 订阅 API ────────────────────────────────────────────────

    def fetch_subscription_collections(self,
                                        limit_once: int = 50) -> List[dict]:
        """获取当前账号订阅的所有合集列表（自动翻页）。"""
        all_colls: List[dict] = []

        resp = self._request("GET", SUBSCRIPTION_URL,
                             params={"offset": 0, "limit": limit_once})
        self._log(f"subscription 首页响应: {str(resp)[:500]}")

        if not resp:
            self._log("subscription: _request 返回 None（网络错误或重试耗尽）")
            return []

        code = resp.get("code")
        if code != 0:
            self._log(f"subscription: API 返回 code={code}, msg={resp.get('msg', resp.get('message', ''))}")
            return []

        if "data" not in resp:
            self._log(f"subscription: 响应中无 'data' 字段，keys={list(resp.keys())}")
            return []

        data  = resp["data"]
        total = data.get("subscribeCollectionCount", 0)
        self._log(f"subscription: 订阅总数={total}")
        all_colls.extend(data.get("collections", []))

        while len(all_colls) < total:
            resp = self._request("GET", SUBSCRIPTION_URL,
                                 params={"offset": len(all_colls),
                                         "limit": limit_once})
            if not resp or resp.get("code") != 0:
                break
            colls = resp.get("data", {}).get("collections", [])
            if not colls:
                break
            all_colls.extend(colls)

        return all_colls

    # ── 图片下载 ────────────────────────────────────────────────

    def download_photo(self, url: str, filepath: str) -> Optional[str]:
        """下载单张图片到指定路径。成功返回路径，失败返回 None。"""
        try:
            parsed = urlparse(url)
            hdrs   = self._headers.copy()
            hdrs["host"] = parsed.netloc
            resp = requests.get(url, headers=hdrs, stream=True, timeout=20)
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                return filepath
        except Exception as e:
            self._log(f"download_photo error {url}: {e}")
        return None

    # ── HTML 内容获取（用于从 URL 提取 post/blog id）──────────────

    def fetch_html(self, url: str, timeout: int = 30) -> Optional[str]:
        """通过浏览器 User-Agent 获取页面 HTML，用于从 URL 中提取 ID。"""
        try:
            browser_hdrs = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            cookies = {USER_COOKIE["name"]: USER_COOKIE["value"]}
            resp = requests.get(url, headers=browser_hdrs,
                                cookies=cookies, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            self._log(f"fetch_html error {url}: {e}")
        return None
