"""
Twitter Thread Generation Workflow

一个简单的workflow，用于生成Twitter thread：
1. 用户输入topic（主题）
2. LLM生成包含outline和tweets的完整结构
3. 输出格式化的Twitter thread
"""

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph

from influflow.ai.state import InfluflowState, Outline, GenerateTweetInput, GenerateTweetOutput
from influflow.ai.prompt import twitter_thread_system_prompt, format_thread_prompt
from influflow.ai.configuration import WorkflowConfiguration
from influflow.ai.utils import get_config_value


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
    
    # 获取输入
    topic = state["topic"]
    language = state["language"]
    
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
    outline: Outline = await structured_llm.ainvoke([
        SystemMessage(content=twitter_thread_system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return {
        "outline": outline
    }


# 构建workflow graph
builder = StateGraph(
    InfluflowState,
    input=GenerateTweetInput,
    output=GenerateTweetOutput,
    config_schema=WorkflowConfiguration
)

# 添加唯一的节点
builder.add_node("generate_tweet_thread", generate_tweet_thread)

# 添加边：从START到节点，从节点到END
builder.add_edge(START, "generate_tweet_thread")
builder.add_edge("generate_tweet_thread", END)

# 编译graph
graph = builder.compile()
