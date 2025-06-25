"""
Article Style and Writing Style Adjustment Module

This module provides functionality to convert articles to different genres and styles, supporting:
- Twitter post format conversion
- Different writing style adjustments
- Style learning based on reference texts
- Custom conversion requirements
"""

from typing import Literal
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from influflow.state import (
    StylerInput,
    StylerOutput, 
    StylerState
)

from influflow.prompts import (
    styler_context_prompt,
    long_tweet_style_prompt,
    STYLE_PROMPTS
)

from influflow.configuration import WorkflowConfiguration
from influflow.utils import get_config_value


async def convert_text_style(state: StylerState, config: RunnableConfig):
    """
    Convert text style in a single LLM call combining style analysis and conversion
    
    This node:
    1. Takes original text, target tag, optional custom prompt and reference text
    2. Uses LLM to analyze reference style (if provided) and convert text in one call
    3. Outputs the final converted text
    
    Args:
        state: Current graph state containing original text, tag, and optional parameters
        config: Configuration including model settings
        
    Returns:
        Dictionary containing the converted text
    """
    
    # Get inputs
    original_text = state["original_text"]
    tag = state["tag"]
    custom_prompt = state.get("custom_prompt", "")
    reference_text = state.get("reference_text", "")
    
    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # Set up conversion model (using writer model for text conversion)
    styler_provider = get_config_value(configurable.styler_provider)
    styler_model_name = get_config_value(configurable.styler_model)
    styler_model_kwargs = get_config_value(configurable.styler_model_kwargs or {})
    conversion_model = init_chat_model(
        model=styler_model_name, 
        model_provider=styler_provider, 
        model_kwargs=styler_model_kwargs
    )
    
    # Select appropriate prompt template based on tag
    if tag in STYLE_PROMPTS:
        prompt_template = STYLE_PROMPTS[tag]
    else:
        prompt_template = STYLE_PROMPTS["generic"]

    if tag in ["long-tweet", "long-tweet-thread"]:
        custom_prompt += long_tweet_style_prompt
    
    # Format conversion instructions
    system_instructions = prompt_template.format(
        tag=tag,
        custom_prompt=custom_prompt
    )
    user_instructions = styler_context_prompt.format(
        original_text=original_text,
        reference_text=reference_text,
    )
    
    # Execute text conversion
    converted_text = await conversion_model.ainvoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=user_instructions)
    ])
    
    return {"styled_text": converted_text.content}


# Build article style adjustment graph
def create_styler_graph():
    """
    Create a simple LangGraph for article style and writing style adjustment
    
    Graph flow:
    1. START -> convert_text_style -> END
    
    Returns:
        Compiled LangGraph instance
    """
    
    # Create state graph
    builder = StateGraph(
        StylerState, 
        input=StylerInput, 
        output=StylerOutput, 
        config_schema=WorkflowConfiguration
    )
    
    # Add node
    builder.add_node("convert_text_style", convert_text_style)
    
    # Add edges
    builder.add_edge(START, "convert_text_style")
    builder.add_edge("convert_text_style", END)
    
    # Compile graph
    return builder.compile()


# Create graph instance
graph = create_styler_graph()


# Convenience function: Quick text style conversion
async def convert_text(
    original_text: str,
    tag: str,
    config: RunnableConfig,
    custom_prompt: str = "",
    reference_text: str = ""
) -> str:
    """
    Convenience function: Direct text style conversion
    
    Args:
        original_text: Original article content
        tag: Target genre tag
        config: Runtime configuration
        custom_prompt: Optional custom prompt
        reference_text: Optional reference text
        
    Returns:
        Converted text
    """
    
    # Prepare input
    input_data = {
        "original_text": original_text,
        "tag": tag,
        "custom_prompt": custom_prompt,
        "reference_text": reference_text
    }
    
    # Execute conversion
    result = await graph.ainvoke(input_data, config)
    
    return result["styled_text"]


# 流式文本转换函数（使用 graph）
async def convert_text_stream(
    original_text: str,
    tag: str,
    config: RunnableConfig,
    custom_prompt: str = "",
    reference_text: str = ""
):
    """
    使用 graph 进行流式文本风格转换
    
    Args:
        original_text: 原始文章内容
        tag: 目标风格标签
        config: 运行时配置
        custom_prompt: 可选的自定义提示词
        reference_text: 可选的参考文本
        
    Yields:
        每次生成的文本片段
    """
    
    # 准备输入数据
    input_data = {
        "original_text": original_text,
        "tag": tag,
        "custom_prompt": custom_prompt,
        "reference_text": reference_text
    }
    
    # 使用 graph 的事件流来获取流式输出
    async for event in graph.astream_events(input_data, config, version="v1"):
        # 过滤出模型调用的流式输出事件
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content


# Supported genre tags list
SUPPORTED_TAGS = list(STYLE_PROMPTS.keys())


def get_supported_tags() -> list[str]:
    """
    Get list of supported genre tags
    
    Returns:
        List of supported genre tags
    """
    return SUPPORTED_TAGS.copy()
