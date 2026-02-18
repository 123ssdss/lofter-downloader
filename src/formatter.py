"""
src/formatter.py
内容格式化工具：HTML 转文本、帖子文本生成、评论文本格式化
"""
import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── HTML → 纯文本 ──────────────────────────────────────────────

def html_to_text(html_content: str) -> str:
    """将 HTML 转为纯文本，保留换行结构。"""
    if not html_content:
        return ""
    text = html.unescape(html_content)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def extract_links_and_titles(html_content: str) -> str:
    """
    将 HTML 中的 <a href> 替换为 "文字 (链接: url)" 格式，
    将 <img src> 替换为 "[图片] url" 格式，然后去除剩余 HTML 标签。
    """
    if not html_content:
        return ""
    text = html.unescape(html_content)

    def _replace_link(m: re.Match) -> str:
        href, inner = m.groups()
        clean = re.sub(r"<[^>]+>", "", inner).strip()
        return f"{clean} (链接: {href})" if clean else href

    def _replace_img(m: re.Match) -> str:
        return f"\n[图片] {m.group(1)}\n"

    text = re.sub(
        r'<a\s+href\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        _replace_link, text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r'<img\s+[^>]*src\s*=\s*["\']([^"\']*)["\'][^>]*>',
        _replace_img, text, flags=re.IGNORECASE
    )
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ── 文件名工具 ─────────────────────────────────────────────────

_UNSAFE = re.compile(r'[\\/*?:"<>|]')


def make_safe_filename(s: str, max_len: int = 100) -> str:
    """将字符串中不合法的文件名字符替换为下划线。"""
    return _UNSAFE.sub("_", s)[:max_len]


def build_post_filename(title: str, author: str,
                        author_id: str = "",
                        prefix: str = "") -> str:
    """
    构造帖子基础文件名（无扩展名）。
    格式：[prefix] title by author[author_id]
    """
    safe_title  = make_safe_filename(title)
    safe_author = make_safe_filename(author)
    name = f"{safe_title} by {safe_author}"
    if author_id:
        name += f"[{make_safe_filename(author_id)}]"
    if prefix:
        name = f"{prefix} {name}"
    return name


# ── 帖子元数据提取 ─────────────────────────────────────────────

def extract_post_metadata(post_detail_json: Dict[str, Any]) -> Dict[str, str]:
    """从 API 返回的帖子详情 JSON 中提取人类可读的元数据。"""
    try:
        record   = post_detail_json["response"]["posts"][0]
        post     = record["post"]
        blog_info = post.get("blogInfo", {})

        publish_ts = post.get("publishTime", 0)
        publish_str = (
            datetime.fromtimestamp(publish_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if publish_ts else ""
        )
        return {
            "title":        post.get("title", "Untitled"),
            "publish_time": publish_str,
            "author":       blog_info.get("blogNickName", "Unknown Author"),
            "blog_name":    blog_info.get("blogName", ""),
            "blog_id":      str(blog_info.get("blogId", "")),
            "blog_url":     post.get("blogPageUrl", ""),
            "tags":         ", ".join(post.get("tagList", [])),
        }
    except (KeyError, IndexError):
        return {
            "title": "Untitled", "publish_time": "", "author": "Unknown",
            "blog_name": "", "blog_id": "", "blog_url": "", "tags": "",
        }


# ── 帖子文本格式化 ─────────────────────────────────────────────

def format_post_as_text(post_detail_json: Dict[str, Any],
                        photo_links: Optional[List[str]] = None,
                        comments_text: Optional[str] = None) -> str:
    """
    将帖子详情格式化为最终的 .txt 文件内容，与原版输出格式完全一致。

    Args:
        comments_text: None = 未下载评论（不输出评论块）；
                       ""   = 下载了但无评论（输出"暂无评论"）；
                       str  = 正常评论文本。
    """
    meta    = extract_post_metadata(post_detail_json)
    content = _extract_post_body(post_detail_json)

    lines: List[str] = [
        f"标题: {meta['title']}",
        f"发布时间: {meta['publish_time']}",
        f"作者: {meta['author']}",
        f"作者LOFTERID: {meta['blog_name']}",
        f"Tags: {meta['tags']}",
        f"Link: {meta['blog_url']}",
        "",
        "[正文]",
        content,
    ]

    if photo_links:
        lines.append("\n\n[Images]")
        lines.extend(photo_links)

    # 只在 comments_text 不为 None 时才输出评论块
    if comments_text is not None:
        lines += ["\n\n\n\n", "【评论】"]
        lines.append(comments_text if comments_text else "(暂无评论)")

    return "\n".join(lines)


def _extract_post_body(post_detail_json: Dict[str, Any]) -> str:
    """提取帖子正文（含彩蛋内容），经过 HTML 清理。"""
    try:
        post = post_detail_json["response"]["posts"][0]["post"]

        # 尝试拼接彩蛋内容
        raw_content = post.get("content", "")
        return_content_list = post.get("returnContent", [])
        if return_content_list:
            gift_text = return_content_list[0].get("content", "")
            if gift_text:
                raw_content = (
                    raw_content
                    + "\n<h3>以下为彩蛋内容</h3>\n"
                    + f'<p id="GiftContent" style="white-space: pre-line;">{gift_text}</p>'
                )

        return extract_links_and_titles(raw_content)
    except (KeyError, IndexError):
        return ""


# ── 评论文本格式化 ─────────────────────────────────────────────

def format_comment(comment: Dict[str, Any], is_reply: bool = False,
                   indent: str = "") -> str:
    """格式化单条评论（含回复列表），与原版格式完全一致。"""
    author    = comment.get("author", {}).get("blogNickName", "Unknown")
    blog_name = comment.get("author", {}).get("blogName", "")
    content   = comment.get("content", "").strip()
    pub_time  = comment.get("publishTimeFormatted", "")
    likes     = comment.get("likeCount", 0)
    ip_loc    = comment.get("ipLocation", "")
    quote     = comment.get("quote", "")
    replies   = comment.get("replies", [])
    emotes    = comment.get("emotes", [])

    result = ""

    if not is_reply:
        result += f"{indent}——————————————————————————\n"

    if quote:
        result += f"{indent}引用：{quote}\n"

    name_str = f"{author}[{blog_name}]" if blog_name else author
    label    = "作者" if is_reply else "发布人"
    result  += f"{indent}{label}：{name_str}\n"
    result  += f"{indent}时间：{pub_time}\n"
    result  += f"{indent}内容：{content}\n"
    result  += f"{indent}点赞数：{likes}\n"

    if ip_loc:
        result += f"{indent}IP属地：{ip_loc}\n"

    if emotes:
        result += f"{indent}表情：\n"
        for e in emotes:
            result += f"{indent}  - {e.get('name', '')} ({e.get('url', '')})\n"

    if replies:
        result += f"{indent}\n————回复列表————\n"
        for idx, reply in enumerate(replies, 1):
            r_author    = reply.get("author", {}).get("blogNickName", "Unknown")
            r_blog_name = reply.get("author", {}).get("blogName", "")
            r_name_str  = f"{r_author}[{r_blog_name}]" if r_blog_name else r_author
            r_quote     = reply.get("quote", "")
            r_ip        = reply.get("ipLocation", "")
            r_emotes    = reply.get("emotes", [])

            if r_quote:
                result += f"{indent}引用：{r_quote}\n"
            result += f"{indent}回复{idx}：\n"
            result += f"{indent}  作者：{r_name_str}\n"
            result += f"{indent}  时间：{reply.get('publishTimeFormatted', '')}\n"
            result += f"{indent}  内容：{reply.get('content', '').strip()}\n"
            result += f"{indent}  点赞数：{reply.get('likeCount', 0)}\n"
            if r_ip:
                result += f"{indent}  IP属地：{r_ip}\n"
            if r_emotes:
                result += f"{indent}  表情：\n"
                for e in r_emotes:
                    result += f"{indent}    - {e.get('name', '')} ({e.get('url', '')})\n"
        result += f"{indent}\n"

    result += f"{indent}\n"
    return result


def format_comments_block(structured: Dict[str, Any]) -> str:
    """
    将结构化评论数据（含 hot_list / all_list）格式化为文本块。
    与原版输出完全一致：先 [热门评论]，再 [全部评论]。
    """
    if not isinstance(structured, dict):
        return ""

    hot_list = structured.get("hot_list", [])
    all_list = structured.get("all_list", [])

    # 最终去重
    seen: set = set()
    unique_all: List[Dict] = []
    for c in all_list:
        cid = c.get("id")
        if cid not in seen:
            unique_all.append(c)
            seen.add(cid)

    result = "[热门评论]\n"
    for c in hot_list:
        result += format_comment(c)

    result += "\n[全部评论]\n"
    for c in unique_all:
        result += format_comment(c)

    return result
