"""
Twitter Thread Generation Workflow

一个简单的workflow，用于生成Twitter thread：
1. 用户输入原始文本（包含主题和可能的语言要求）
2. 分析用户输入，提取topic和language
3. LLM生成包含outline和tweets的完整结构
4. 输出格式化的Twitter thread
"""

from typing import cast
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from pydantic import BaseModel, Field

from influflow.ai.state import InfluflowState, Outline, GenerateTweetOutput, UserInput, UserInputAnalysis
from influflow.ai.prompt import twitter_thread_system_prompt, format_thread_prompt
from influflow.ai.configuration import WorkflowConfiguration
from influflow.ai.utils import get_config_value


async def user_input_analysis(state: InfluflowState, config: RunnableConfig):
    """分析用户输入，提取主题和语言
    
    这个节点：
    1. 接收用户的原始输入
    2. 调用LLM分析用户想要写的主题
    3. 判断用户希望的输出语言
    4. 返回topic和language供下一个节点使用
    
    Args:
        state: 当前状态，包含user_input
        config: 配置信息
        
    Returns:
        包含topic和language的字典
    """
    # 获取用户输入
    user_input = state.get("user_input", "")
    
    # 初始化模型并设置结构化输出
    analyzer_model = init_chat_model(
        model="gpt-4o-mini",
        model_provider="openai",
        temperature=0.1  # 低温度以获得更一致的分析结果
    )
    structured_analyzer = analyzer_model.with_structured_output(UserInputAnalysis)
    
    # 分析用户输入的系统提示词
    analysis_system_prompt = """You are an AI assistant that analyzes user input to extract:
1. The main topic they want to write a Twitter thread about
2. The language they want the output to be in

Rules:
- Extract the core topic clearly and concisely
- For language detection:
  - If the user explicitly mentions a language (e.g., "in Chinese", "用中文"), use that language
  - If no language is mentioned, infer from the input language:
    - Chinese input → output in "Chinese"
    - English input → output in "English"
    - Other languages → output in that language
  - Default to "English" if uncertain
- Be precise and avoid adding interpretation beyond what the user expressed"""
    
    # 分析用户输入
    analysis = cast(UserInputAnalysis, await structured_analyzer.ainvoke([
        SystemMessage(content=analysis_system_prompt),
        HumanMessage(content=f"Please analyze this user input and extract the topic and desired output language:\n\n{user_input}")
    ]))
    
    # 处理返回值 - LangChain返回的应该已经是UserInputAnalysis实例
    if hasattr(analysis, 'topic') and hasattr(analysis, 'language'):
        return {
            "topic": analysis.topic,
            "language": analysis.language
        }
    else:
        # 如果结构不对，提供默认值
        return {
            "topic": user_input,  # 使用原始输入作为主题
            "language": "English"  # 默认使用英文
        }


async def generate_tweet_thread(state: InfluflowState, config: RunnableConfig):
    """生成Twitter thread的核心节点
    
    这个节点：
    1. 获取用户输入的topic
    2. 调用LLM生成结构化的outline，包含两层结构和tweets
    3. 返回完整的大纲结构
    
    Args:
        state: 当前状态，包含topic等输入信息
        config: 配置信息，包含模型设置
        
    Returns:
        包含outline的字典
    """
    
    # 获取输入 - 使用安全的get方法访问可选字段
    topic = state.get("topic")
    language = state.get("language")
    
    # 检查必需的字段是否存在
    if not topic:
        raise ValueError("Topic is required but not found in state")
    if not language:
        raise ValueError("Language is required but not found in state")
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 设置生成模型
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_temperature = get_config_value(configurable.writer_temperature)
    
    # 初始化模型并设置结构化输出
    writer_model = init_chat_model(
        model=writer_model_name, 
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs,
        temperature=writer_temperature
    )
    structured_llm = writer_model.with_structured_output(Outline)
    
    # 格式化提示词（使用topic，暂时不使用tone和target_audience）
    user_prompt = format_thread_prompt(topic, language)
    # 调用LLM生成outline
    outline = await structured_llm.ainvoke([
        SystemMessage(content=twitter_thread_system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return {
        "outline": outline
    }


# 构建workflow graph
builder = StateGraph(
    InfluflowState,
    input=UserInput,
    output=GenerateTweetOutput,
    config_schema=WorkflowConfiguration
)

# 添加节点
builder.add_node("user_input_analysis", user_input_analysis)
builder.add_node("generate_tweet_thread", generate_tweet_thread)

# 添加边：START -> user_input_analysis -> generate_tweet_thread -> END
builder.add_edge(START, "user_input_analysis")
builder.add_edge("user_input_analysis", "generate_tweet_thread")
builder.add_edge("generate_tweet_thread", END)

# 编译graph
graph = builder.compile()
