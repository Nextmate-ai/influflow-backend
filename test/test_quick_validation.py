# -*- coding: utf-8 -*-
"""
Quick Validation Script

快速验证脚本，测试单个主题并显示详细输出，用于快速调试格式问题。
"""

import asyncio
import re
import sys
import os

# 导入项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from influflow.graph.generate_tweet import graph


async def quick_test():
    """快速测试"""
    print("🚀 快速验证测试")
    print("=" * 50)
    
    # 测试配置
    topic = "AI tools for content creators"
    config = {
        "configurable": {
            "writer_provider": "openai",
            "writer_model": "gpt-4o-mini",
            "writer_model_kwargs": {}
        }
    }
    
    input_state = {
        "topic": topic,
        "language": "English"
    }
    
    print(f"📝 测试主题: {topic}")
    print("⏳ 正在生成...")
    
    try:
        # 生成
        result = await graph.ainvoke(input_state, config)
        thread_text = result.get("tweet_thread", "")
        
        print("✅ 生成完成！")
        print("\n" + "=" * 50)
        print("📱 生成的 Twitter Thread:")
        print("=" * 50)
        print(thread_text)
        
        # 解析和验证
        print("\n" + "=" * 50)
        print("🔍 详细验证结果:")
        print("=" * 50)
        
        tweets = re.findall(r'\((\d+)/\d+\)(.*?)(?=\n\(\d+/\d+\)|$)', thread_text, re.DOTALL)
        
        for tweet_num, content in tweets:
            content = content.strip()
            char_count = len(content)
            char_valid = 250 <= char_count <= 275
            
            # 检查bullet points
            has_bullets = '•' in content
            bullet_valid = True
            if has_bullets:
                same_line_bullets = re.search(r'•[^•\n]*•', content)
                bullet_valid = not bool(same_line_bullets)
            
            print(f"\nTweet {tweet_num}:")
            print(f"  📏 字符数: {char_count} {'✅' if char_valid else '❌'} (需要250-275)")
            if has_bullets:
                print(f"  📝 Bullet格式: {'✅' if bullet_valid else '❌'}")
            print(f"  📄 内容: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            if not char_valid or (has_bullets and not bullet_valid):
                print(f"  ⚠️  问题:", end="")
                if not char_valid:
                    print(f" 字符数{char_count}不在范围内", end="")
                if has_bullets and not bullet_valid:
                    print(f" Bullet points没有正确换行", end="")
                print()
        
        # 统计
        total_tweets = len(tweets)
        char_valid_count = sum(1 for _, content in tweets if 250 <= len(content.strip()) <= 275)
        bullet_tweets = [(num, content) for num, content in tweets if '•' in content.strip()]
        bullet_valid_count = sum(1 for _, content in bullet_tweets if not re.search(r'•[^•\n]*•', content.strip()))
        
        print(f"\n📊 总体统计:")
        print(f"  📝 总推文数: {total_tweets}")
        print(f"  📏 字符数达标: {char_valid_count}/{total_tweets} ({char_valid_count/total_tweets*100:.1f}%)")
        print(f"  📝 包含bullet的推文: {len(bullet_tweets)}")
        if bullet_tweets:
            print(f"  ✅ Bullet格式正确: {bullet_valid_count}/{len(bullet_tweets)} ({bullet_valid_count/len(bullet_tweets)*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ 生成失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(quick_test()) 