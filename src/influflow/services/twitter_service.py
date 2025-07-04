"""
Twitter AI服务层
抽取Twitter相关的业务逻辑，供API和UI共同使用
"""

import asyncio
from typing import Dict, Any, Optional
import concurrent.futures

from langchain_core.runnables import RunnableConfig
from influflow.ai.graph.generate_tweet import graph
from influflow.ai.graph.modify_single_tweet import graph as modify_graph
from influflow.ai.graph.modify_outline_structure import graph as modify_outline_graph
from influflow.ai.graph.generate_image import graph as image_graph
from influflow.ai.state import Outline, OutlineNode, OutlineLeafNode


class TwitterService:
    """Twitter AI功能服务类"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def get_default_config(model: str = "gpt-4.1") -> Dict[str, Any]:
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
    
    async def generate_thread_async(self, user_input: str, config: Dict[str, Any], personalization=None):
        """异步生成Twitter thread"""
        try:
            # 准备输入数据 - 包含user_input和可选的personalization
            input_data = {"user_input": user_input}
            if personalization:
                input_data["personalization"] = personalization
            
            # 流式获取结果
            final_result = None
            # 将dict转换为RunnableConfig类型
            runnable_config: RunnableConfig = config  # type: ignore
            async for event in graph.astream(input_data, runnable_config):
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
            # 将dict转换为RunnableConfig类型
            runnable_config: RunnableConfig = config  # type: ignore
            async for event in modify_graph.astream(input_data, runnable_config):
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
            # 将dict转换为RunnableConfig类型
            runnable_config: RunnableConfig = config  # type: ignore
            async for event in modify_outline_graph.astream(input_data, runnable_config):
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
    
    async def generate_image_async(self, target_tweet: str, tweet_thread: str, config: Dict[str, Any], image_quality: str = "medium"):
        """异步为推文生成图片"""
        try:
            # 准备输入数据
            input_data = {
                "target_tweet": target_tweet,
                "tweet_thread": tweet_thread,
                "image_quality": image_quality
            }
            
            # 流式获取结果
            final_result = None
            # 将dict转换为RunnableConfig类型
            runnable_config: RunnableConfig = config  # type: ignore
            async for event in image_graph.astream(input_data, runnable_config):
                if event:
                    final_result = event
            
            if final_result and 'call_openai_image_api' in final_result:
                # 从最终状态中获取图片URL和prompt
                api_result = final_result['call_openai_image_api']
                image_url = api_result.get("image_url", "")
                image_prompt = api_result.get("image_prompt", "")
                
                # 如果call_openai_image_api没有返回prompt，尝试从generate_image_prompt获取
                if not image_prompt and 'generate_image_prompt' in final_result:
                    image_prompt = final_result['generate_image_prompt'].get("image_prompt", "")
                
                # 如果还是没有找到，尝试从根级别获取
                if not image_prompt:
                    image_prompt = final_result.get("image_prompt", "")
                
                return {
                    "status": "success",
                    "data": {
                        "image_url": image_url,
                        "image_prompt": image_prompt
                    }
                }
            else:
                return {"status": "error", "error": "No result from image generation"}
                
        except Exception as e:
            return {"status": "error", "error": f"Image generation error: {str(e)}"}
    
    def generate_thread(self, user_input: str, model: str = "gpt-4.1", personalization=None):
        """生成Twitter thread"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.generate_thread_async(user_input, config, personalization))
    
    def modify_tweet(self, outline: Outline, tweet_number: int, modification_prompt: str, model: str = "gpt-4.1"):
        """修改单个Tweet"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.modify_tweet_async(outline, tweet_number, modification_prompt, config))
    
    def modify_outline(self, original_outline: Outline, new_outline_structure: Outline, model: str = "gpt-4.1"):
        """修改Outline结构"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.modify_outline_async(original_outline, new_outline_structure, config))
    
    def generate_image(self, target_tweet: str, tweet_thread: str, model: str = "gpt-4.1", image_quality: str = "medium"):
        """为推文生成图片"""
        config = self.get_default_config(model)
        return self.safe_asyncio_run(self.generate_image_async(target_tweet, tweet_thread, config, image_quality))


# 创建全局服务实例
twitter_service = TwitterService() 