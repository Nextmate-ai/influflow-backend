"""
Twitter Thread Generation Workflow

一个简单的workflow，用于生成Twitter thread：
1. 用户输入原始文本（包含主题和可能的语言要求）
2. 分析用户输入，提取topic和language
3. LLM生成包含outline和tweets的完整结构
4. 输出格式化的Twitter thread
"""

from typing import cast, Optional, Dict, Any, Callable
import json
import re
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.config import get_stream_writer

from influflow.ai.state import InfluflowState, Outline, OutlineNode, OutlineLeafNode, GenerateTweetOutput, UserInput, UserInputAnalysis, Personalization
from influflow.ai.prompt import twitter_thread_system_prompt, twitter_thread_user_prompt
from influflow.ai.configuration import WorkflowConfiguration
from influflow.ai.utils import get_config_value


def parse_streaming_json(text: str) -> list[Dict[str, Any]]:
    """解析流式JSON，提取完整的推文数据
    
    Args:
        text: 累积的JSON文本
        
    Returns:
        解析出的完整推文数据列表
    """
    results = []
    
    # 尝试按行解析JSON
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 尝试解析单行JSON
        try:
            if line.startswith('{') and line.endswith('}'):
                data = json.loads(line)
                results.append(data)
        except json.JSONDecodeError:
            # 如果解析失败，尝试修复常见的JSON格式问题
            try:
                # 移除可能的尾随逗号
                fixed_line = re.sub(r',\s*}', '}', line)
                fixed_line = re.sub(r',\s*]', ']', fixed_line)
                data = json.loads(fixed_line)
                results.append(data)
            except json.JSONDecodeError:
                continue
    
    return results




def format_thread_prompt(topic: str, language: str, personalization: Optional[Personalization]) -> str:
    """格式化生成Twitter thread的用户提示词
    
    Args:
        topic: 推文主题
        language: 输出语言
        personalization: 个性化设置对象（可选）
        
    Returns:
        格式化后的用户提示词
    """
    # 构建个性化信息部分
    personalization_info = ""
    
    if personalization:
      personalization_info = personalization.format_personalization()
    
    return twitter_thread_user_prompt.format(
        topic=topic, 
        language=language,
        personalization_info=personalization_info
    )


async def user_input_analysis(state: InfluflowState, config: RunnableConfig):
    """分析用户输入，提取主题和语言
    
    这个节点：
    1. 接收用户的原始输入
    2. 调用LLM分析用户想要写的主题
    3. 判断用户希望的输出语言
    4. 返回topic和language供下一个节点使用
    
    Args:
        state: 当前状态，包含user_input
        config: 配置信息 (LangGraph节点必需参数)
        
    Returns:
        包含topic和language的字典
    """
    # config参数是LangGraph节点的必需接口，虽然在此函数中未直接使用
    _ = config  # 明确标记config参数已知晓但在此处不需要
    
    # 获取流式写入器以发送自定义进度更新
    writer = get_stream_writer()

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
    result = None
    if hasattr(analysis, 'topic') and hasattr(analysis, 'language'):
        result = {
            "topic": analysis.topic,
            "language": analysis.language
        }
    else:
        # 如果结构不对，提供默认值
        result = {
            "topic": user_input,  # 使用原始输入作为主题
            "language": "English"  # 默认使用英文
        }
    
    # 发送分析完成进度更新
    if writer:
        writer({
            "stage": "analysis", 
            "message": f"Analysis completed: topic='{result['topic']}', language='{result['language']}'",
            "data": result
        })
    
    return result


async def generate_tweet_thread_stream(state: InfluflowState, config: RunnableConfig) -> Dict[str, Any]:
    """流式生成Twitter thread的核心节点
    
    这个节点使用LangGraph原生流式特性：
    1. 获取用户输入的topic和language
    2. 使用get_stream_writer()发送自定义进度更新
    3. 流式调用LLM生成推文
    4. 逐步解析JSON并发送进度更新
    
    Args:
        state: 当前状态，包含topic等输入信息
        config: 配置信息，包含模型设置
        
    Returns:
        包含outline的字典
    """
    
    # 获取输入 - 使用安全的get方法访问可选字段
    topic = state.get("topic")
    language = state.get("language")
    personalization = state.get("personalization", None)
    
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
    
    # 初始化模型（不使用structured_output）
    writer_model = init_chat_model(
        model=writer_model_name, 
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs,
        temperature=writer_temperature
    )
    
    # 格式化提示词
    user_prompt = format_thread_prompt(topic, language, personalization)
    
    # 发送模型初始化进度更新
    writer = get_stream_writer()
    
    # 流式调用LLM
    accumulated_text = ""
    processed_lines = set()  # 避免重复处理相同的JSON行
    stream_data = []  # 收集所有流式数据用于构建最终结果
    total_tweets = 0  # 跟踪已生成的推文数量
    
    async for chunk in writer_model.astream([
        SystemMessage(content=twitter_thread_system_prompt),
        HumanMessage(content=user_prompt)
    ]):
        if hasattr(chunk, 'content') and chunk.content:
            # 确保content是字符串类型
            content = chunk.content
            if isinstance(content, str):
                accumulated_text += content
            
            # 尝试解析完整的JSON行
            parsed_data = parse_streaming_json(accumulated_text)
            
            for data in parsed_data:
                # 创建一个唯一标识符来避免重复处理
                data_id = f"{data.get('type', '')}_{data.get('tweet_number', 0)}"
                
                if data_id not in processed_lines:
                    processed_lines.add(data_id)
                    stream_data.append(data)
                    
                    # 发送实时进度更新
                    if writer:
                        if data.get('type') == 'tweet':
                            total_tweets += 1
                            writer({
                                "stage": "generation",
                                "message": f"Generated tweet #{total_tweets}",
                                "tweet_data": data
                            })
                        elif data.get('type') == 'topic':
                            writer({
                                "stage": "generation",
                                "message": f"Topic identified: {data.get('topic', '')}",
                                "topic_data": data
                            })
                        elif data.get('type') == 'section':
                            writer({
                                "stage": "generation",
                                "message": f"Starting new section: {data.get('title', '')}",
                                "section_data": data
                            })
    
    # 构建最终的Outline结构
    if writer:
        writer({"stage": "generation", "message": "Building final result..."})
    
    outline = build_outline_from_stream_data(stream_data)
    
    # 发送完成进度更新
    if writer:
        writer({
            "stage": "generation",
            "message": f"Generation completed! Total {total_tweets} tweets",
            "completed": True,
            "final_outline": outline
        })
    
    return {"outline": outline}


def build_outline_from_stream_data(stream_data: list[Dict[str, Any]]) -> Outline:
    """从流式数据构建Outline结构
    
    Args:
        stream_data: 流式输出的数据列表
        
    Returns:
        构建好的Outline对象
    """
    topic_data = None
    sections_data: Dict[str, list[Dict[str, Any]]] = {}  # {section_title: [tweets]}
    current_section = None
    
    # 整理数据
    for data in stream_data:
        if data.get("type") == "topic":
            topic_data = data
        elif data.get("type") == "section":
            current_section = data.get("title", "Default Section")
            if current_section not in sections_data:
                sections_data[current_section] = []
        elif data.get("type") == "tweet":
            section_title = data.get("section_title", current_section or "Default Section")
            if section_title not in sections_data:
                sections_data[section_title] = []
            sections_data[section_title].append(data)
    
    # 如果没有明确的section，创建一个默认section
    if not sections_data:
        sections_data["Twitter Thread"] = []
        for data in stream_data:
            if data.get("type") == "tweet":
                sections_data["Twitter Thread"].append(data)
    
    # 构建OutlineNode列表
    nodes = []
    for section_title, tweets in sections_data.items():
        if tweets:  # 只添加有推文的section
            leaf_nodes = []
            for tweet in sorted(tweets, key=lambda x: x.get("tweet_number", 0)):
                leaf_nodes.append(OutlineLeafNode(
                    title=tweet.get("title", ""),
                    tweet_number=tweet.get("tweet_number", 0),
                    tweet_content=tweet.get("tweet_content", "")
                ))
            
            nodes.append(OutlineNode(
                title=section_title,
                leaf_nodes=leaf_nodes
            ))
    
    # 创建完整的Outline
    outline = Outline(
        topic=topic_data.get("topic", "") if topic_data else "Generated Thread",
        nodes=nodes
    )
    
    return outline


# 原有的generate_tweet_thread_with_streaming函数不再需要，
# 因为现在generate_tweet_thread_stream直接返回完整结果




# 构建workflow graph - 使用流式生成版本
builder = StateGraph(
    InfluflowState,
    input=UserInput,
    output=GenerateTweetOutput,
    config_schema=WorkflowConfiguration
)

# 添加节点 - 使用改进的流式生成版本
builder.add_node("user_input_analysis", user_input_analysis)
builder.add_node("generate_tweet_thread", generate_tweet_thread_stream)

# 添加边：START -> user_input_analysis -> generate_tweet_thread -> END
builder.add_edge(START, "user_input_analysis")
builder.add_edge("user_input_analysis", "generate_tweet_thread")
builder.add_edge("generate_tweet_thread", END)

# 编译graph
graph = builder.compile()

async def enhanced_streaming_graph_runner(input_data: Dict[str, Any], config: RunnableConfig):
    """使用LangGraph原生流式特性的新流式运行器"""
    try:
        # 使用LangGraph的原生流式模式运行graph
        # 支持多种流式模式: updates, custom, messages
        async for stream_mode, chunk in graph.astream(
            input_data,
            config,
            stream_mode=["updates", "custom"]
        ):
            if stream_mode == "updates":
                # 处理状态更新
                if isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        yield {
                            "status": "node_update",
                            "node": node_name,
                            "data": node_output
                        }
                else:
                    # 处理非字典格式的更新
                    yield {
                        "status": "raw_update",
                        "data": chunk
                    }
            elif stream_mode == "custom":
                # 处理自定义进度更新
                yield {
                    "status": "progress",
                    "data": chunk
                }
    except Exception as e:
        # 增强的错误处理
        error_info = {
            "status": "error", 
            "error": str(e),
            "error_type": type(e).__name__,
            "stage": "graph_execution"
        }
        yield error_info


# 为了兼容性，保留原有的函数名
streaming_graph_runner = enhanced_streaming_graph_runner


# 导出流式生成函数供直接调用
__all__ = ["graph", "generate_tweet_thread_stream", "build_outline_from_stream_data", "user_input_analysis", "streaming_graph_runner"]
