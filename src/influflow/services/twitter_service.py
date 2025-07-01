"""
Twitter AI服务层
抽取Twitter相关的业务逻辑，供API和UI共同使用
"""

import asyncio
from typing import Dict, Any, Optional
import concurrent.futures

from influflow.ai.graph.generate_tweet import graph
from influflow.ai.graph.modify_single_tweet import graph as modify_graph
from influflow.ai.graph.modify_outline_structure import graph as modify_outline_graph
from influflow.ai.state import Outline, OutlineNode, OutlineLeafNode


class TwitterService:
    """Twitter AI功能服务类"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def get_default_config(model: str = "gpt-4o-mini") -> Dict[str, Any]:
        """获取默认AI配置"""
        return {
            "configurable": {
                "writer_provider": "openai",
                "writer_model": model
            }
        }
    
    @staticmethod
    def safe_asyncio_run(coro):
        """
        安全地在同步环境中运行异步协程，特别是在Streamlit或FastAPI中
        """
        try:
            try:
                # 尝试获取当前线程中正在运行的事件循环
                asyncio.get_running_loop()
                
                # 如果存在正在运行的循环，在一个新线程中运行协程以避免冲突
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()

            except RuntimeError:
                # 如果没有正在运行的循环，直接运行
                return asyncio.run(coro)
                
        except Exception as e:
            print(f"Error in async operation: {e}")
            return {"status": "error", "error": f"Async execution error: {str(e)}"}
    
    async def generate_thread_async(self, topic: str, language: str, config: Dict[str, Any]):
        """异步生成Twitter thread"""
        try:
            # 准备输入数据 - 包含topic和language
            input_data = {"topic": topic, "language": language}
            
            # 流式获取结果
            final_result = None
            async for event in graph.astream(input_data, config):
                # 保存最后的结果
                if event:
                    final_result = event
                    
            # 返回最终结果
            if final_result and 'generate_tweet_thread' in final_result:
                return {
                    "status": "success",
                    "data": final_result['generate_tweet_thread']
                }
            else:
                return {"status": "error", "error": "No result generated"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def modify_tweet_async(self, outline: Outline, tweet_number: int, modification_prompt: str, config: Dict[str, Any]):
        """异步修改单个Tweet"""
        try:
            # 准备输入数据
            # LangGraph的astream会自动处理Pydantic模型的序列化
            input_data = {
                "outline": outline,
                "tweet_number": tweet_number,
                "modification_prompt": modification_prompt
            }
            
            # 流式获取结果
            final_result = None
            async for event in modify_graph.astream(input_data, config):
                if event:
                    final_result = event
            
            if final_result and 'modify_single_tweet' in final_result:
                return {
                    "status": "success",
                    "data": {
                        "updated_tweet": final_result['modify_single_tweet'].get("updated_tweet", "")
                    }
                }
            else:
                return {"status": "error", "error": "No result from modification"}
                
        except Exception as e:
            return {"status": "error", "error": f"Async modification error: {str(e)}"}
    
    async def modify_outline_async(self, original_outline: Outline, new_outline_structure: Outline, config: Dict[str, Any]):
        """异步修改Outline结构"""
        try:
            # 准备输入数据
            # LangGraph的astream会自动处理Pydantic模型的序列化
            input_data = {
                "original_outline": original_outline,
                "new_outline_structure": new_outline_structure,
            }
            
            # 流式获取结果
            final_result = None
            async for event in modify_outline_graph.astream(input_data, config):
                if event:
                    final_result = event
            
            if final_result and 'modify_outline_structure' in final_result:
                return {
                    "status": "success",
                    "data": final_result['modify_outline_structure']
                }
            else:
                return {"status": "error", "error": "No result from outline modification"}
                
        except Exception as e:
            return {"status": "error", "error": f"Async outline modification error: {str(e)}"}
    
    def generate_thread(self, topic: str, language: str = "English", model: str = "gpt-4.1"):
        """生成Twitter thread"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.generate_thread_async(topic, language, config))
    
    def modify_tweet(self, outline: Outline, tweet_number: int, modification_prompt: str, model: str = "gpt-4.1"):
        """修改单个Tweet"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.modify_tweet_async(outline, tweet_number, modification_prompt, config))
    
    def modify_outline(self, original_outline: Outline, new_outline_structure: Outline, model: str = "gpt-4.1"):
        """修改Outline结构"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.modify_outline_async(original_outline, new_outline_structure, config))


# 创建全局服务实例
twitter_service = TwitterService() 