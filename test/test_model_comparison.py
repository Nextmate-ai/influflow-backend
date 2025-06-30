# -*- coding: utf-8 -*-
"""
Model Comparison Test

比较 GPT-4.1 vs GPT-4o 在 bullet point 格式遵守方面的表现
"""

import asyncio
import re
import sys
import os

# 导入项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from influflow.graph.generate_tweet import graph


async def test_model_formatting(model_name: str, topic: str):
    """测试特定模型的格式遵守能力"""
    print(f"\n🧪 测试模型: {model_name}")
    print(f"📝 主题: {topic}")
    print("-" * 50)
    
    config = {
        "configurable": {
            "writer_provider": "openai",
            "writer_model": model_name,
            "writer_model_kwargs": {}
        }
    }
    
    input_state = {
        "topic": topic,
        "language": "English"
    }
    
    try:
        result = await graph.ainvoke(input_state, config)
        thread_text = result.get("tweet_thread", "")
        
        # 解析推文
        tweets = re.findall(r'\((\d+)/\d+\)(.*?)(?=\n\(\d+/\d+\)|$)', thread_text, re.DOTALL)
        
        bullet_stats = {
            "total_tweets": len(tweets),
            "tweets_with_bullets": 0,
            "correct_bullet_format": 0,
            "incorrect_examples": []
        }
        
        for tweet_num, content in tweets:
            content = content.strip()
            
            if '•' in content:
                bullet_stats["tweets_with_bullets"] += 1
                
                # 检查是否有同行的 bullets
                same_line_bullets = re.search(r'•[^•\n]*•', content)
                
                if same_line_bullets:
                    bullet_stats["incorrect_examples"].append({
                        "tweet_num": tweet_num,
                        "problem": "同行多个bullets",
                        "content": content[:100] + "..."
                    })
                else:
                    bullet_stats["correct_bullet_format"] += 1
        
        # 打印结果
        print(f"✅ 生成完成")
        print(f"📊 总推文: {bullet_stats['total_tweets']}")
        print(f"📝 包含bullets: {bullet_stats['tweets_with_bullets']}")
        
        if bullet_stats["tweets_with_bullets"] > 0:
            success_rate = bullet_stats["correct_bullet_format"] / bullet_stats["tweets_with_bullets"] * 100
            print(f"✅ Bullet格式正确: {bullet_stats['correct_bullet_format']}/{bullet_stats['tweets_with_bullets']} ({success_rate:.1f}%)")
            
            if bullet_stats["incorrect_examples"]:
                print(f"❌ 格式错误示例:")
                for example in bullet_stats["incorrect_examples"][:2]:
                    print(f"   Tweet {example['tweet_num']}: {example['content']}")
        
        return bullet_stats
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return None


async def run_comparison():
    """运行模型对比测试"""
    print("🚀 GPT-4.1 vs GPT-4o Bullet Point 格式对比测试")
    print("=" * 60)
    
    topic = "Digital marketing strategies for small businesses"
    
    models = [
        "gpt-4o-mini",  # 作为对照组
        "gpt-4o", 
        "gpt-4-1106-preview"  # GPT-4.1
    ]
    
    results = {}
    
    for model in models:
        result = await test_model_formatting(model, topic)
        results[model] = result
        await asyncio.sleep(2)  # 避免API限制
    
    # 对比分析
    print("\n" + "=" * 60)
    print("📈 对比分析结果")
    print("=" * 60)
    
    for model, stats in results.items():
        if stats:
            tweets_with_bullets = stats["tweets_with_bullets"]
            if tweets_with_bullets > 0:
                success_rate = stats["correct_bullet_format"] / tweets_with_bullets * 100
                print(f"\n{model}:")
                print(f"  Bullet格式正确率: {success_rate:.1f}%")
                print(f"  错误数量: {len(stats['incorrect_examples'])}")
            else:
                print(f"\n{model}: 没有生成包含bullets的推文")
    
    # 显示一个完整示例
    if results.get("gpt-4-1106-preview"):
        print(f"\n" + "=" * 60)
        print("📱 GPT-4.1 完整输出示例:")
        print("=" * 60)
        
        config = {
            "configurable": {
                "writer_provider": "openai", 
                "writer_model": "gpt-4-1106-preview",
                "writer_model_kwargs": {}
            }
        }
        
        input_state = {
            "topic": topic,
            "language": "English"
        }
        
        try:
            result = await graph.ainvoke(input_state, config)
            thread_text = result.get("tweet_thread", "")
            print(thread_text)
        except Exception as e:
            print(f"无法获取完整示例: {str(e)}")


if __name__ == "__main__":
    asyncio.run(run_comparison()) 