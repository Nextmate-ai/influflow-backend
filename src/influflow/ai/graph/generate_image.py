"""
Twitter Thread Image Generation Workflow

一个为推文生成配图的workflow：
1. 接收目标推文和推文串上下文
2. 通过大模型分析推文内容，生成适合的图片生成prompt
3. 调用OpenAI DALL-E API生成图片
4. 返回生成的图片URL和使用的prompt
"""

import os
from typing import cast
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
import openai

from influflow.ai.state import GenerateImageState, GenerateImageInput, GenerateImageOutput, ImagePrompt
from influflow.ai.prompt import generate_image_prompt_system_prompt, format_generate_image_prompt
from influflow.ai.configuration import WorkflowConfiguration
from influflow.ai.utils import get_config_value


async def generate_image_prompt(state: GenerateImageState, config: RunnableConfig):
    """生成图片prompt的节点
    
    这个节点：
    1. 分析目标推文和推文串上下文
    2. 调用LLM生成适合的DALL-E图片生成prompt
    3. 返回包含prompt和风格描述的结构化输出
    
    Args:
        state: 当前状态，包含target_tweet、tweet_thread等信息
        config: 配置信息
        
    Returns:
        包含image_prompt_obj的字典
    """
    # 获取输入数据
    target_tweet = state.get("target_tweet")
    tweet_thread = state.get("tweet_thread")
    
    # 检查必需的字段
    if not target_tweet:
        raise ValueError("Target tweet is required but not found in state")
    if not tweet_thread:
        raise ValueError("Tweet thread is required but not found in state")
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 设置生成模型
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_temperature = get_config_value(configurable.writer_temperature)
    
    # 初始化模型并设置结构化输出
    model = init_chat_model(
        model=writer_model_name,
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs,
        temperature=writer_temperature
    )
    structured_model = model.with_structured_output(ImagePrompt)
    
    # 格式化用户提示词
    user_prompt = format_generate_image_prompt(target_tweet, tweet_thread)
    
    # 调用LLM生成图片prompt
    image_prompt_obj = cast(ImagePrompt, await structured_model.ainvoke([
        SystemMessage(content=generate_image_prompt_system_prompt),
        HumanMessage(content=user_prompt)
    ]))
    
    return {
        "image_prompt_obj": image_prompt_obj,
        "image_prompt": image_prompt_obj.prompt  # 同时保存字符串形式供后续使用
    }


async def call_openai_image_api(state: GenerateImageState, config: RunnableConfig):
    """调用OpenAI DALL-E API生成图片的节点
    
    这个节点：
    1. 获取前一步生成的图片prompt
    2. 调用OpenAI DALL-E API生成图片
    3. 返回生成的图片URL
    
    Args:
        state: 当前状态，包含image_prompt等信息
        config: 配置信息
        
    Returns:
        包含image_url的字典
    """
    # 获取图片prompt
    image_prompt_obj = state.get("image_prompt_obj")
    image_prompt = state.get("image_prompt")
    
    if not image_prompt_obj and not image_prompt:
        raise ValueError("Image prompt is required but not found in state")
    
    # 如果没有字符串形式的prompt，从对象中提取
    if not image_prompt and image_prompt_obj:
        image_prompt = image_prompt_obj.prompt
    
    # 确保prompt不为空
    if not image_prompt:
        raise ValueError("Image prompt cannot be empty")
    
    # 检查OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required for image generation")
    
    # 初始化OpenAI客户端
    client = openai.AsyncOpenAI(api_key=openai_api_key)
    
    try:
        # 调用OpenAI图片生成API
        response = await client.images.generate(
            model="dall-e-3",  # 使用DALL-E 3模型
            prompt=image_prompt,
            size="1024x1024",  # 方形图片，适合社交媒体
            quality="standard"  # 图片质量设置：standard 或 hd
        )
        
        # 检查响应并提取图片URL
        if response.data and len(response.data) > 0:
            image_url = response.data[0].url
        else:
            raise ValueError("No image data returned from OpenAI API")
        
        return {
            "image_url": image_url,
            "image_prompt": image_prompt  # 返回生成图片使用的prompt
        }
        
    except Exception as e:
        # 如果API调用失败，返回错误信息
        raise ValueError(f"Failed to generate image: {str(e)}")


# 构建workflow graph
builder = StateGraph(
    GenerateImageState,
    input=GenerateImageInput,
    output=GenerateImageOutput,
    config_schema=WorkflowConfiguration
)

# 添加节点
builder.add_node("generate_image_prompt", generate_image_prompt)
builder.add_node("call_openai_image_api", call_openai_image_api)

# 添加边：START -> generate_image_prompt -> call_openai_image_api -> END
builder.add_edge(START, "generate_image_prompt")
builder.add_edge("generate_image_prompt", "call_openai_image_api")
builder.add_edge("call_openai_image_api", END)

# 编译graph
graph = builder.compile()
