# Lofter 爬虫项目

## 项目概述

这是一个Lofter内容爬虫工具
品鉴此项目代码前请注意：此工程的某些部分存在有一些奇怪的写法以及可能存在暗病和屎山！！！！！！
图一乐，AI写的代码水平不高,只是简单用用

#
### 输出目录结构
- `json/`：存储抓取的原始 JSON 数据
- `photo/`：存储下载的图片
- `output/`：存储格式化的文本输出
- `logs/`：存储日志文件

## 安装和使用

### 1. 克隆项目

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 安装依赖

```bash
pip install requests
```

### 3. 配置认证信息

将您的 Lofter 认证信息添加到 `config.py` 文件中：

```python
USER_COOKIE = {
    "name": "COOKIE name",
    "value": "your_phone_login_auth_here"
}
```
### cookie 说明
        "1": "lofter id 登录 (Authorization)",
        "2": "手机号登录 (LOFTER-PHONE-LOGIN-AUTH)",
        "3": "QQ登录/微信登录/微博登录 (LOFTER_SESS)",
        "4": "邮箱登录 (NTES_SESS)",
括号内容为cookie名称 对应登录方式修改name和value即可

### 4. 使用方法

```bash
python main.py <mode> [value] [options]
```

#### 模式选项:
- `tag`: 按标签抓取内容
- `blog`: 抓取指定博客的帖子
- `comment`: 抓取帖子评论
- `collection`: 抓取收藏集内容
- `subscription`: 抓取订阅内容

#### 参数:

**必选参数:**
- `mode`: 运行模式 (tag, blog, comment, collection, subscription)

**可选参数:**
- `value`: 模式特定值 (如标签名、帖子ID、收藏集ID) 
- `--blog_id`: 博客ID (在 blog 和 comment 模式中需要)
- `--list_type`: 标签模式下的列表类型 (默认: total)
- `--timelimit`: 标签模式下的时间限制
- `--blog_type`: 标签模式下的博客类型 (默认: 1)
- `--no-comments`: 禁用评论下载
- `--no-photos`: 禁用图片下载
- `--debug`: 启用调试日志

#### 使用示例:

1. 抓取特定标签下的内容:
```bash
python main.py tag "lofter-art" --list_type total
```

2. 抓取多个标签的内容:
```bash
python main.py tag "lofter-art" "digital-art" "illustration"
```

3. 抓取特定博客的帖子:
```bash
python main.py blog <post_id> --blog_id <blog_id>
```

4. 抓取帖子评论:
```bash
python main.py comment <post_id> --blog_id <blog_id>
```

5. 抓取合集内容:
```bash
python main.py collection <collection_id>
```

6. 抓取订阅合集列表内容 (需要认证信息):
```bash
python main.py subscription 
```

## 配置文件

### config.py
项目配置文件包含以下设置：
- 网络请求配置 (超时时间等)
- 速率限制 (请求间隔时间)
  - REQUEST_DELAY：通用请求间隔时间（秒）
  - TAG_POST_REQUEST_DELAY：标签帖子请求间隔时间（秒）
  - COLLECTION_REQUEST_DELAY：合集请求间隔时间（秒）
  - POST_DETAIL_REQUEST_DELAY：帖子详情请求间隔时间（秒）
  - COMMENT_REQUEST_DELAY：评论请求间隔时间（秒）
  - BETWEEN_PAGES_DELAY：页面间请求间隔时间（秒）
  - BETWEEN_BATCHES_DELAY：批处理间间隔时间（秒）
- 并发设置 (图片和文本下载的线程数)
  - PHOTO_MAX_WORKERS：图片下载最大线程数
  - TEXT_MAX_WORKERS：文本处理最大线程数
  - COMMENT_MAX_WORKERS：评论处理最大线程数
- 默认参数设置

