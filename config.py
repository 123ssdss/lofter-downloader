"""
Lofter 下载器 - 全局配置文件
所有可调节的参数均在此处配置（不含 cookie，cookie 见 cookie.py）
"""
import os

# ── 目录配置 ─────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
JSON_DIR   = os.path.join(BASE_DIR, "json")
PHOTO_DIR  = os.path.join(BASE_DIR, "photo")
LOGS_DIR   = os.path.join(BASE_DIR, "logs")

for _d in (OUTPUT_DIR, JSON_DIR, PHOTO_DIR, LOGS_DIR):
    os.makedirs(_d, exist_ok=True)

# ── 网络请求 ──────────────────────────────────────────────────
REQUEST_TIMEOUT = 15
MAX_RETRIES     = 3

# ── 速率限制（秒） ────────────────────────────────────────────
REQUEST_DELAY             = 1.0
TAG_POST_REQUEST_DELAY    = 0.05
COLLECTION_REQUEST_DELAY  = 0.5
POST_DETAIL_REQUEST_DELAY = 0.2
BETWEEN_PAGES_DELAY       = 0.5
BETWEEN_BATCHES_DELAY     = 1.0

# ── 评论延迟（秒） ────────────────────────────────────────────
COMMENT_REQUEST_DELAY    = 0.05
L2_COMMENT_REQUEST_DELAY = 1.0
COMMENT_MAX_WORKERS      = 5

# ── 并发 ──────────────────────────────────────────────────────
PHOTO_MAX_WORKERS    = 5   # 图片下载线程数（始终生效）
TEXT_MAX_WORKERS     = 10
DEFAULT_POST_WORKERS = 1   # 帖子级并发（1 = 单线程，--threads N 可覆盖）

# ── 标签默认参数 ──────────────────────────────────────────────
DEFAULT_LIST_TYPE  = "total"
DEFAULT_TIME_LIMIT = ""     # 空字符串 = 不限制时间
DEFAULT_BLOG_TYPE  = "0"
