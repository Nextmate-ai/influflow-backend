# -*- coding: utf-8 -*-
"""
End-to-End Twitter Thread Generation Test

简化的端到端测试，专注于英文场景，验证字符数和bullet point换行。
运行10次测试不同的topic，检查输出质量。
"""

import asyncio
import re
import time
from typing import Dict, List, Any
import unittest
from unittest.mock import patch

# 导入项目模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from influflow.graph import graph
from influflow.configuration import WorkflowConfiguration


class EndToEndValidator:
    """端到端验证器"""
    
    @staticmethod
    def validate_character_count(tweet: str) -> Dict[str, Any]:
        """验证字符数 (250-275)"""
        char_count = len(tweet)
        is_valid = 250 <= char_count <= 275
        return {
            "char_count": char_count,
            "is_valid": is_valid,
            "issue": None if is_valid else f"字符数 {char_count} 不在 250-275 范围内"
        }
    
    @staticmethod
    def validate_bullet_points(tweet: str) -> Dict[str, Any]:
        """验证bullet points是否正确换行"""
        has_bullets = '•' in tweet
        if not has_bullets:
            return {"has_bullets": False, "is_valid": True, "issue": None}
        
        # 检查是否有同行的多个bullet points
        same_line_bullets = re.search(r'•[^•\n]*•', tweet)
        
        return {
            "has_bullets": True,
            "is_valid": not bool(same_line_bullets),
            "issue": "Bullet points没有正确换行" if same_line_bullets else None
        }
    
    @classmethod
    def validate_thread(cls, thread_text: str) -> Dict[str, Any]:
        """验证整个thread"""
        # 解析tweets
        tweets = re.findall(r'\((\d+)/\d+\)(.*?)(?=\n\(\d+/\d+\)|$)', thread_text, re.DOTALL)
        
        results = {
            "total_tweets": len(tweets),
            "tweet_results": [],
            "summary": {
                "char_valid_count": 0,
                "bullet_valid_count": 0,
                "total_with_bullets": 0,
                "all_issues": []
            }
        }
        
        for tweet_num, content in tweets:
            content = content.strip()
            
            char_result = cls.validate_character_count(content)
            bullet_result = cls.validate_bullet_points(content)
            
            tweet_result = {
                "tweet_number": int(tweet_num),
                "content": content,
                "char_validation": char_result,
                "bullet_validation": bullet_result,
                "is_valid": char_result["is_valid"] and bullet_result["is_valid"]
            }
            
            results["tweet_results"].append(tweet_result)
            
            # 统计
            if char_result["is_valid"]:
                results["summary"]["char_valid_count"] += 1
            else:
                results["summary"]["all_issues"].append(f"Tweet {tweet_num}: {char_result['issue']}")
                
            if bullet_result["has_bullets"]:
                results["summary"]["total_with_bullets"] += 1
                if bullet_result["is_valid"]:
                    results["summary"]["bullet_valid_count"] += 1
                else:
                    results["summary"]["all_issues"].append(f"Tweet {tweet_num}: {bullet_result['issue']}")
        
        return results


class TestEndToEnd(unittest.TestCase):
    """端到端测试"""
    
    def setUp(self):
        """设置测试"""
        self.test_topics = [
            "AI tools for content creators",
            "Remote work productivity tips", 
            "Cryptocurrency investment basics",
            "Social media marketing strategies",
            "Python programming for beginners",
            "Digital nomad lifestyle guide",
            "E-commerce business startup",
            "Personal finance management",
            "Sustainable living practices",
            "Time management techniques"
        ]
        
        self.validator = EndToEndValidator()
        self.all_results = []
    
    async def run_single_test(self, topic: str, test_index: int) -> Dict[str, Any]:
        """运行单个测试"""
        print(f"\n🧪 测试 [{test_index+1}/10] 主题: {topic}")
        
        # 配置
        config = {
            "configurable": {
                "writer_provider": "openai",
                "writer_model": "gpt-4.1",
                "writer_model_kwargs": {"temperature": 0.7}
            }
        }
        
        # 输入状态
        input_state = {
            "topic": topic,
            "language": "English"
        }
        
        try:
            # 运行生成
            start_time = time.time()
            result = await graph.ainvoke(input_state, config)
            end_time = time.time()
            
            generation_time = end_time - start_time
            thread_text = result.get("tweet_thread", "")
            
            # 验证结果
            validation_result = self.validator.validate_thread(thread_text)
            
            test_result = {
                "test_index": test_index,
                "topic": topic,
                "generation_time": generation_time,
                "thread_text": thread_text,
                "validation": validation_result,
                "success": True
            }
            
            # 打印简要结果
            summary = validation_result["summary"]
            total_tweets = validation_result["total_tweets"]
            print(f"✅ 测试 [{test_index+1}/10] 完成 ({generation_time:.1f}s)")
            print(f"📊 结果: {total_tweets}条推文")
            print(f"📏 字符数达标: {summary['char_valid_count']}/{total_tweets}")
            if summary["total_with_bullets"] > 0:
                print(f"📝 Bullet格式正确: {summary['bullet_valid_count']}/{summary['total_with_bullets']}")
            
            if summary["all_issues"]:
                print(f"⚠️  问题:")
                for issue in summary["all_issues"][:3]:  # 只显示前3个问题
                    print(f"   - {issue}")
                if len(summary["all_issues"]) > 3:
                    print(f"   - ... 还有 {len(summary['all_issues']) - 3} 个问题")
            
            return test_result
            
        except Exception as e:
            print(f"❌ 测试 [{test_index+1}/10] 失败: {str(e)}")
            return {
                "test_index": test_index,
                "topic": topic,
                "generation_time": 0,
                "thread_text": "",
                "validation": None,
                "success": False,
                "error": str(e)
            }
    
    async def run_all_tests(self):
        """并发运行所有测试"""
        print("🚀 开始端到端测试 - 10个主题并发执行")
        print("=" * 60)
        
        # 创建所有测试任务
        test_tasks = []
        for i, topic in enumerate(self.test_topics):
            task = self.run_single_test(topic, i)
            test_tasks.append(task)
        
        # 并发执行所有测试
        start_time = time.time()
        print(f"📝 启动 {len(test_tasks)} 个并发测试任务...")
        
        try:
            # 使用 asyncio.gather 并发执行
            results = await asyncio.gather(*test_tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            print(f"\n🎉 所有测试完成！总耗时: {total_time:.1f}秒")
            
            # 处理结果，包括异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # 如果是异常，创建失败结果
                    self.all_results.append({
                        "test_index": i,
                        "topic": self.test_topics[i],
                        "generation_time": 0,
                        "thread_text": "",
                        "validation": None,
                        "success": False,
                        "error": str(result)
                    })
                    print(f"❌ 测试 [{i+1}/10] 发生异常: {str(result)}")
                else:
                    self.all_results.append(result)
            
            # 按测试索引排序结果
            self.all_results.sort(key=lambda x: x["test_index"])
            
        except Exception as e:
            print(f"❌ 并发执行过程中发生错误: {str(e)}")
            raise
        
        return self.all_results
    
    def analyze_results(self):
        """分析所有结果"""
        print("\n" + "=" * 60)
        print("📈 总体分析结果")
        print("=" * 60)
        
        successful_tests = [r for r in self.all_results if r["success"]]
        failed_tests = [r for r in self.all_results if not r["success"]]
        
        print(f"✅ 成功生成: {len(successful_tests)}/10")
        print(f"❌ 生成失败: {len(failed_tests)}/10")
        
        if failed_tests:
            print(f"\n失败的主题:")
            for test in failed_tests:
                print(f"  - 测试 [{test['test_index']+1}] {test['topic']}: {test.get('error', 'Unknown error')}")
        
        if successful_tests:
            # 字符数分析
            total_tweets = sum(r["validation"]["total_tweets"] for r in successful_tests)
            total_char_valid = sum(r["validation"]["summary"]["char_valid_count"] for r in successful_tests)
            char_success_rate = (total_char_valid / total_tweets * 100) if total_tweets > 0 else 0
            
            print(f"\n📏 字符数分析:")
            print(f"  - 总推文数: {total_tweets}")
            print(f"  - 字符数达标: {total_char_valid} ({char_success_rate:.1f}%)")
            
            # Bullet point分析
            total_with_bullets = sum(r["validation"]["summary"]["total_with_bullets"] for r in successful_tests)
            total_bullet_valid = sum(r["validation"]["summary"]["bullet_valid_count"] for r in successful_tests)
            bullet_success_rate = (total_bullet_valid / total_with_bullets * 100) if total_with_bullets > 0 else 0
            
            print(f"\n📝 Bullet Point分析:")
            print(f"  - 包含bullet的推文: {total_with_bullets}")
            print(f"  - 格式正确: {total_bullet_valid} ({bullet_success_rate:.1f}%)")
            
            # 生成时间分析
            avg_time = sum(r["generation_time"] for r in successful_tests) / len(successful_tests)
            min_time = min(r["generation_time"] for r in successful_tests)
            max_time = max(r["generation_time"] for r in successful_tests)
            
            print(f"\n⏱️  生成时间分析:")
            print(f"  - 平均时间: {avg_time:.1f}秒")
            print(f"  - 最快: {min_time:.1f}秒")
            print(f"  - 最慢: {max_time:.1f}秒")
            
            # 详细问题统计
            all_issues = []
            for test in successful_tests:
                all_issues.extend(test["validation"]["summary"]["all_issues"])
            
            if all_issues:
                print(f"\n⚠️  发现的问题类型:")
                issue_types = {}
                for issue in all_issues:
                    if "字符数" in issue:
                        issue_types["字符数问题"] = issue_types.get("字符数问题", 0) + 1
                    elif "Bullet" in issue:
                        issue_types["Bullet格式问题"] = issue_types.get("Bullet格式问题", 0) + 1
                
                for issue_type, count in issue_types.items():
                    print(f"  - {issue_type}: {count}次")
    
    def test_end_to_end_generation(self):
        """主测试方法"""
        async def run_test():
            await self.run_all_tests()
            self.analyze_results()

            
            successful_tests = [r for r in self.all_results if r["success"]]
            self.assertTrue(len(successful_tests) >= 5, f"至少5个测试应该成功，实际成功 {len(successful_tests)} 个")
        
        # 运行异步测试
        asyncio.run(run_test())


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2) 