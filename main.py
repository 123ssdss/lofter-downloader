"""
Lofter 下载器 v2 — 入口文件
用法：
  python main.py tag   <标签名> [<标签名2> ...]  [选项]
  python main.py blog  <帖子URL或ID>             [--blog_id ID] [选项]
  python main.py comment <帖子ID>               --blog_id ID   [选项]
  python main.py collection <合集ID>             [选项]
  python main.py subscription                    [选项]

公共选项：
  --no-comments   不下载评论
  --no-photos     不下载图片
  --threads N     帖子级并发线程数（默认 1，即单线程）
  --debug         开启调试日志

标签专用选项：
  --list_type     列表类型（默认 total）
  --timelimit     时间限制（默认不限制）
  --blog_type     博客类型（默认 0）
"""
import argparse
import sys
import time

import config
from src.core.api_client import LofterClient
from src.logger import StatusDisplay
from src.services.blog_service import BlogService
from src.services.collection_service import CollectionService
from src.services.subscription_service import SubscriptionService
from src.services.tag_service import TagService


def _format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="Lofter 内容下载器",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "mode",
        choices=["tag", "blog", "comment", "collection", "subscription"],
        help="运行模式",
    )
    p.add_argument(
        "value",
        nargs="*",
        default=None,
        help="目标值（标签名、帖子ID/URL、合集ID）",
    )
    p.add_argument("--blog_id",   help="博客ID（blog / comment 模式必须提供）")
    p.add_argument("--list_type", default=config.DEFAULT_LIST_TYPE,
                   help="标签列表类型（默认 total）")
    p.add_argument("--timelimit", default=config.DEFAULT_TIME_LIMIT,
                   help="标签时间限制（默认不限制）")
    p.add_argument("--blog_type", default=config.DEFAULT_BLOG_TYPE,
                   help="博客类型（默认 0）")
    p.add_argument("--no-comments", action="store_true", help="不下载评论")
    p.add_argument("--no-photos",   action="store_true", help="不下载图片")
    p.add_argument("--threads",     type=int, default=config.DEFAULT_POST_WORKERS,
                   help=f"帖子级并发线程数（默认 {config.DEFAULT_POST_WORKERS}，即单线程）")
    p.add_argument("--debug",       action="store_true", help="开启调试日志")
    return p


def run(args: argparse.Namespace) -> dict:
    client = LofterClient(debug=args.debug)
    mode   = args.mode
    values = args.value or []
    dl_comments = not args.no_comments
    dl_images   = not args.no_photos
    workers     = max(1, args.threads)

    # ── tag 模式 ─────────────────────────────────────────────
    if mode == "tag":
        tags = [v for v in values if v]
        if not tags:
            StatusDisplay.print_error("标签模式需要至少一个标签名称")
            return {"success": False}
        svc = TagService(client, args.debug)
        return svc.process(
            tags=tags,
            list_type=args.list_type,
            timelimit=args.timelimit,
            blog_type=args.blog_type,
            download_comments=dl_comments,
            download_images=dl_images,
            post_workers=workers,
        )

    # ── blog 模式 ────────────────────────────────────────────
    if mode == "blog":
        if not values:
            StatusDisplay.print_error("blog 模式需要提供帖子 URL 或 ID")
            return {"success": False}
        post_id = values[0].strip("\"'")
        is_url  = post_id.startswith("http://") or post_id.startswith("https://")
        if not is_url and not args.blog_id:
            StatusDisplay.print_error("非 URL 模式下需要提供 --blog_id 参数")
            return {"success": False}
        svc = BlogService(client, args.debug)
        r   = svc.download_post_by_id(
            post_id=post_id,
            blog_id=args.blog_id,
            download_comments=True,   # blog 模式总是下载评论
            download_images=dl_images,
        )
        return {
            "success":         r.success,
            "base_filename":   r.base_filename,
            "processed_files": [r.text_file, r.json_file] + r.photo_files,
            "error":           r.error,
        }

    # ── comment 模式 ─────────────────────────────────────────
    if mode == "comment":
        if not values or not args.blog_id:
            StatusDisplay.print_error("comment 模式需要提供帖子 ID 和 --blog_id 参数")
            return {"success": False}
        post_id = values[0].strip("\"'")
        # comment 模式：下载帖子详情 + 评论，不下载图片
        svc = BlogService(client, args.debug)
        r   = svc.download_post_by_id(
            post_id=post_id,
            blog_id=args.blog_id,
            download_comments=True,
            download_images=False,
        )
        return {
            "success":        r.success,
            "post_id":        r.post_id,
            "comments_count": 0,   # 不再逐行统计
            "error":          r.error,
        }

    # ── collection 模式 ──────────────────────────────────────
    if mode == "collection":
        if not values:
            StatusDisplay.print_error("collection 模式需要提供合集 ID")
            return {"success": False}
        collection_id = values[0].strip("\"'")
        svc = CollectionService(client, args.debug)
        return svc.process(
            collection_id=collection_id,
            download_comments=dl_comments,
            download_images=dl_images,
            post_workers=workers,
        )

    # ── subscription 模式 ────────────────────────────────────
    if mode == "subscription":
        svc = SubscriptionService(client, args.debug)
        return svc.process()

    return {"success": False, "error": f"未知模式: {mode}"}


def print_result(mode: str, result: dict, elapsed: float) -> None:
    StatusDisplay.print_header("爬取完成")
    StatusDisplay.print_info(f"总用时: {_format_time(elapsed)}")

    if not result:
        StatusDisplay.print_warning("没有返回结果")
        return

    if result.get("success"):
        StatusDisplay.print_success("所有任务处理成功！")
        StatusDisplay.print_section("处理详情")

        if mode == "tag":
            StatusDisplay.print_info(
                f"标签处理: {result.get('processed_tags', 0)}/{result.get('total_tags', 0)}"
            )
            StatusDisplay.print_info(
                f"帖子处理: {result.get('total_posts_processed', 0)} 成功 / "
                f"{result.get('total_posts_failed', 0)} 失败"
            )
        elif mode == "blog":
            files = result.get("processed_files", [])
            StatusDisplay.print_info(f"文件保存: {len([f for f in files if f])} 个")
        elif mode == "collection":
            StatusDisplay.print_info(f"合集名称: {result.get('collection_name', '?')}")
            StatusDisplay.print_info(
                f"帖子处理: {result.get('processed_posts', 0)}/{result.get('total_posts', 0)}"
            )
        elif mode == "subscription":
            StatusDisplay.print_info(f"订阅总数: {result.get('total_subscriptions', 0)}")
            StatusDisplay.print_info(f"未读数量: {result.get('total_unread', 0)}")
        elif mode == "comment":
            StatusDisplay.print_info(f"帖子ID: {result.get('post_id', '?')}")
    else:
        StatusDisplay.print_error("处理失败")
        msg = result.get("error") or result.get("message") or result.get("msg")
        if msg:
            StatusDisplay.print_error(f"错误信息: {msg}")

    print("=" * 60)


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # ── 显示启动横幅 ──────────────────────────────────────────
    header_info = {
        "运行模式": args.mode,
        "调试模式": "启用" if args.debug else "禁用",
        "评论下载": "禁用" if args.no_comments else "启用",
        "图片下载": "禁用" if args.no_photos else "启用",
        "并发线程": args.threads,
    }
    if args.value:
        header_info["参数值"] = ", ".join(str(v) for v in args.value if v)
    if args.blog_id:
        header_info["博客ID"] = args.blog_id

    StatusDisplay.print_header("Lofter 下载器 v2", header_info)

    start_time = time.time()
    result: dict = {}

    try:
        result = run(args)
    except KeyboardInterrupt:
        StatusDisplay.print_warning("\n操作被用户中断")
        sys.exit(0)
    except Exception as e:
        StatusDisplay.print_error(f"处理过程中发生未捕获异常: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    print_result(args.mode, result, time.time() - start_time)


if __name__ == "__main__":
    main()
