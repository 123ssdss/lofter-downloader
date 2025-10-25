"""
测试真实帖子的评论处理
使用重构后的评论模块
"""
import sys
import json
from network import LofterClient
from processors.comment_processor_refactored import process_comments
from processors.comment_fetcher import CommentFetcher
from processors.comment_formatter import CommentFormatter
from processors.comment_saver import CommentSaver
from utils.cookie_manager import load_cookies


def test_refactored_comments(post_id, blog_id):
    """测试重构后的评论处理"""
    print("=" * 70)
    print("测试重构后的评论模块")
    print("=" * 70)
    print(f"帖子ID: {post_id}")
    print(f"博客ID: {blog_id}")
    print()
    
    # 加载cookies
    print("步骤 1: 加载Cookie配置...")
    cookie_config = load_cookies()
    cookies = cookie_config.get("cookies", {})
    
    if not any(cookies.values()):
        print("⚠️  警告: 未找到有效的Cookie，可能无法获取评论")
        print("提示: 运行 'python main.py cookie_setup' 设置Cookie")
        print()
    
    # 创建客户端（启用调试模式）
    print("步骤 2: 创建Lofter客户端...")
    client = LofterClient(cookies=cookies, debug=True)
    print()
    
    # 方式1: 使用整合接口
    print("-" * 70)
    print("测试方式 1: 使用整合接口 process_comments()")
    print("-" * 70)
    try:
        comments_text = process_comments(
            client, 
            post_id, 
            blog_id, 
            mode='comment', 
            name='test_post'
        )
        
        if comments_text:
            print(f"✓ 成功获取评论")
            print(f"✓ 评论文本长度: {len(comments_text)} 字符")
            print()
            print("评论内容预览:")
            print("-" * 70)
            # 显示前500字符
            preview = comments_text[:500]
            print(preview)
            if len(comments_text) > 500:
                print("...")
                print(f"(还有 {len(comments_text) - 500} 个字符)")
        else:
            print("⚠️  未找到评论或评论为空")
        
        print()
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # 方式2: 使用模块化方式
    print("-" * 70)
    print("测试方式 2: 使用模块化方式")
    print("-" * 70)
    try:
        # 创建各个组件
        fetcher = CommentFetcher(client)
        formatter = CommentFormatter()
        saver = CommentSaver(client)
        
        print("步骤 2.1: 获取评论数据...")
        structured_comments = fetcher.fetch_all_comments(post_id, blog_id)
        
        if structured_comments:
            hot_count = len(structured_comments.get("hot_list", []))
            all_count = len(structured_comments.get("all_list", []))
            
            print(f"✓ 成功获取评论数据")
            print(f"  - 热门评论: {hot_count} 条")
            print(f"  - 全部评论: {all_count} 条")
            print()
            
            # 显示评论详情
            if all_count > 0:
                print("评论详情:")
                for idx, comment in enumerate(structured_comments["all_list"][:3], 1):
                    author = comment.get("author", {}).get("blogNickName", "Unknown")
                    content = comment.get("content", "")[:50]
                    replies_count = len(comment.get("replies", []))
                    print(f"  {idx}. {author}: {content}...")
                    if replies_count > 0:
                        print(f"     └─ {replies_count} 条回复")
                
                if all_count > 3:
                    print(f"  ... 还有 {all_count - 3} 条评论")
                print()
            
            print("步骤 2.2: 保存评论...")
            saver.save_comments(post_id, blog_id, structured_comments, mode='comment', name='test_post')
            print("✓ 评论已保存到文件")
            print()
            
            print("步骤 2.3: 格式化评论...")
            formatted_text = formatter.format_comments(structured_comments)
            print(f"✓ 评论已格式化")
            print(f"  - 格式化文本长度: {len(formatted_text)} 字符")
            print()
            
            # 显示格式化结果
            print("格式化内容预览:")
            print("-" * 70)
            preview = formatted_text[:400]
            print(preview)
            if len(formatted_text) > 400:
                print("...")
                print(f"(还有 {len(formatted_text) - 400} 个字符)")
            print()
            
        else:
            print("⚠️  未找到评论")
            print()
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # 检查保存的文件
    print("-" * 70)
    print("检查保存的文件")
    print("-" * 70)
    import os
    
    # 检查JSON文件
    json_files = [
        f"json/comments/comments_{post_id}_{blog_id}.json",
        f"json/comments/comments_formatted_{post_id}_{blog_id}.txt"
    ]
    
    for filepath in json_files:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"✓ {filepath} ({size} bytes)")
        else:
            print(f"✗ {filepath} (未找到)")
    
    print()
    print("=" * 70)
    print("测试完成")
    print("=" * 70)


def main():
    """主函数"""
    # 使用提供的测试数据
    post_id = "11794253202"
    blog_id = "537732885"
    
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "重构评论模块真实测试" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    test_refactored_comments(post_id, blog_id)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
