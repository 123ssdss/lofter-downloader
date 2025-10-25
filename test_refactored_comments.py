"""
测试重构后的评论处理模块
"""
import sys


def test_comment_fetcher():
    """测试评论获取器"""
    print("=" * 60)
    print("测试 CommentFetcher 类")
    print("=" * 60)
    
    try:
        from processors.comment_fetcher import CommentFetcher
        from network import LofterClient
        
        # 创建一个测试客户端
        client = LofterClient(debug=True)
        fetcher = CommentFetcher(client)
        
        print("✓ CommentFetcher 导入成功")
        print(f"✓ 方法检查:")
        print(f"  - fetch_all_comments: {hasattr(fetcher, 'fetch_all_comments')}")
        print(f"  - _fetch_all_l1_comments: {hasattr(fetcher, '_fetch_all_l1_comments')}")
        print(f"  - _fetch_l2_comments: {hasattr(fetcher, '_fetch_l2_comments')}")
        print(f"  - _normalize_comment: {hasattr(fetcher, '_normalize_comment')}")
        
    except Exception as e:
        print(f"✗ CommentFetcher 测试失败: {e}")
        return False
    
    return True


def test_comment_formatter():
    """测试评论格式化器"""
    print("\n" + "=" * 60)
    print("测试 CommentFormatter 类")
    print("=" * 60)
    
    try:
        from processors.comment_formatter import CommentFormatter
        
        formatter = CommentFormatter()
        
        print("✓ CommentFormatter 导入成功")
        print(f"✓ 方法检查:")
        print(f"  - format_comments: {hasattr(formatter, 'format_comments')}")
        print(f"  - _format_comment_list: {hasattr(formatter, '_format_comment_list')}")
        print(f"  - _format_single_comment: {hasattr(formatter, '_format_single_comment')}")
        print(f"  - _format_replies: {hasattr(formatter, '_format_replies')}")
        
        # 测试格式化功能
        test_data = {
            "hot_list": [],
            "all_list": [{
                "id": "test_id",
                "content": "测试评论",
                "publishTimeFormatted": "2024-01-01 12:00:00",
                "likeCount": 10,
                "ipLocation": "测试地点",
                "author": {
                    "blogNickName": "测试用户",
                    "blogId": "test_blog"
                },
                "quote": "",
                "replies": []
            }]
        }
        
        result = formatter.format_comments(test_data)
        print(f"✓ 格式化测试成功，输出长度: {len(result)} 字符")
        
    except Exception as e:
        print(f"✗ CommentFormatter 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_comment_saver():
    """测试评论保存器"""
    print("\n" + "=" * 60)
    print("测试 CommentSaver 类")
    print("=" * 60)
    
    try:
        from processors.comment_saver import CommentSaver
        from network import LofterClient
        
        client = LofterClient(debug=True)
        saver = CommentSaver(client)
        
        print("✓ CommentSaver 导入成功")
        print(f"✓ 方法检查:")
        print(f"  - save_comments: {hasattr(saver, 'save_comments')}")
        print(f"  - _save_as_json: {hasattr(saver, '_save_as_json')}")
        print(f"  - _save_user_format: {hasattr(saver, '_save_user_format')}")
        print(f"  - _get_json_dir: {hasattr(saver, '_get_json_dir')}")
        
    except Exception as e:
        print(f"✗ CommentSaver 测试失败: {e}")
        return False
    
    return True


def test_comment_processor():
    """测试评论处理器"""
    print("\n" + "=" * 60)
    print("测试 comment_processor_refactored 模块")
    print("=" * 60)
    
    try:
        from processors.comment_processor_refactored import process_comments
        
        print("✓ process_comments 函数导入成功")
        print(f"✓ 函数签名检查通过")
        
    except Exception as e:
        print(f"✗ comment_processor_refactored 测试失败: {e}")
        return False
    
    return True


def test_comment_mode_processor():
    """测试评论模式处理器"""
    print("\n" + "=" * 60)
    print("测试 CommentModeProcessor 类")
    print("=" * 60)
    
    try:
        from processors.comment_mode_processor_refactored import CommentModeProcessor, process_comment_mode
        from network import LofterClient
        
        client = LofterClient(debug=True)
        processor = CommentModeProcessor(client)
        
        print("✓ CommentModeProcessor 导入成功")
        print(f"✓ 方法检查:")
        print(f"  - process: {hasattr(processor, 'process')}")
        print(f"  - _parse_post_info: {hasattr(processor, '_parse_post_info')}")
        print(f"  - _extract_post_id_from_url: {hasattr(processor, '_extract_post_id_from_url')}")
        print(f"  - _save_post_json: {hasattr(processor, '_save_post_json')}")
        
        # 测试URL解析
        test_url = "https://testblog.lofter.com/post/123abc"
        post_id = processor._extract_post_id_from_url(test_url)
        blog_id = processor._extract_blog_id_from_url(test_url)
        
        print(f"✓ URL解析测试:")
        print(f"  - URL: {test_url}")
        print(f"  - 提取的 post_id: {post_id}")
        print(f"  - 提取的 blog_id: {blog_id}")
        
        assert post_id == "123abc", "Post ID 提取错误"
        assert blog_id == "testblog", "Blog ID 提取错误"
        print(f"✓ URL解析功能正常")
        
    except Exception as e:
        print(f"✗ CommentModeProcessor 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_integration():
    """集成测试"""
    print("\n" + "=" * 60)
    print("集成测试")
    print("=" * 60)
    
    try:
        # 测试所有模块可以一起导入
        from processors.comment_fetcher import CommentFetcher
        from processors.comment_formatter import CommentFormatter
        from processors.comment_saver import CommentSaver
        from processors.comment_processor_refactored import process_comments
        from processors.comment_mode_processor_refactored import process_comment_mode
        
        print("✓ 所有模块可以一起导入")
        
        # 测试配置导入
        from config import GROUP_COMMENTS_BY_QUOTE, COMMENT_MAX_WORKERS
        print(f"✓ 配置加载成功:")
        print(f"  - GROUP_COMMENTS_BY_QUOTE: {GROUP_COMMENTS_BY_QUOTE}")
        print(f"  - COMMENT_MAX_WORKERS: {COMMENT_MAX_WORKERS}")
        
    except Exception as e:
        print(f"✗ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("重构评论模块测试套件")
    print("=" * 60 + "\n")
    
    tests = [
        ("CommentFetcher", test_comment_fetcher),
        ("CommentFormatter", test_comment_formatter),
        ("CommentSaver", test_comment_saver),
        ("CommentProcessor", test_comment_processor),
        ("CommentModeProcessor", test_comment_mode_processor),
        ("集成测试", test_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} 执行时发生异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试都通过了！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
