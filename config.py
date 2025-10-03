# Lofter爬虫项目配置文件
import os

# 基础路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 输出目录配置
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
JSON_DIR = os.path.join(BASE_DIR, 'json')
PHOTO_DIR = os.path.join(BASE_DIR, 'photo')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# 创建基础目录
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# 网络请求配置
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

# 速率限制配置
# 基础请求延迟配置
REQUEST_DELAY = 1  # 通用请求间隔时间（秒）
TAG_POST_REQUEST_DELAY = 0.05  # 标签帖子请求间隔时间（秒）
COLLECTION_REQUEST_DELAY = 0.2  # 合集请求间隔时间（秒）
POST_DETAIL_REQUEST_DELAY = 0.1  # 帖子详情请求间隔时间（秒）
COMMENT_REQUEST_DELAY = 0.5  # 评论请求间隔时间（秒）
BETWEEN_PAGES_DELAY = 0.5  # 页面间请求间隔时间（秒）
BETWEEN_BATCHES_DELAY = 1.0  # 批处理间间隔时间（秒）

# 并发配置
PHOTO_MAX_WORKERS = 5
TEXT_MAX_WORKERS = 8
COMMENT_MAX_WORKERS = 6  # 评论处理的最大工作线程数

# 数据处理配置
DEFAULT_LIST_TYPE = "total"
DEFAULT_TIME_LIMIT = ""
DEFAULT_BLOG_TYPE = "1"