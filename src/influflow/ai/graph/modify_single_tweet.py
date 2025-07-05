"""
单个Tweet修改Workflow

用于修改已生成的Twitter thread中的单个tweet：
1. 收集完整的推文串提供给LLM作为上下文
2. 根据用户的修改提示词重新生成tweet内容
3. 更新outline并保持整体thread的连贯性
"""

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph

from influflow.ai.state import (
    ModifySingleTweetState, 
    Outline, 
    ModifySingleTweetInput,
    ModifySingleTweetOutput
)
from influflow.ai.configuration import WorkflowConfiguration
from influflow.ai.utils import get_config_value
from influflow.ai.prompt import modify_single_tweet_system_prompt, format_modify_single_tweet_prompt


async def modify_single_tweet(state: ModifySingleTweetState, config: RunnableConfig):
    """修改单个tweet的完整流程
    
    这个节点完成全部工作：
    1. 收集完整的推文串作为上下文
    2. 调用LLM生成新的tweet内容
    3. 更新outline并返回结果
    
    Args:
        state: 包含outline、tweet编号和修改提示的状态
        config: 配置信息
        
    Returns:
        包含更新后outline的字典
    """
    outline_data = state["outline"]
    tweet_number = state["tweet_number"]
    modification_prompt = state["modification_prompt"]
    
    # 处理outline数据类型：如果是字典则转换为Outline对象
    if isinstance(outline_data, dict):
        outline = Outline.model_validate(outline_data)
    else:
        outline = outline_data
    
    # 步骤1：收集所有tweets
    # 收集所有tweets并找到要修改的tweet
    all_tweets = []
    target_tweet_info = None
    
    for node_idx, node in enumerate(outline.nodes):
        for leaf_idx, leaf_node in enumerate(node.leaf_nodes):
            all_tweets.append({
                "tweet_number": leaf_node.tweet_number,
                "content": leaf_node.tweet_content,
                "title": leaf_node.title,
                "node_idx": node_idx,
                "leaf_idx": leaf_idx,
                "section_title": node.title
            })
            
            if leaf_node.tweet_number == tweet_number:
                target_tweet_info = {
                    "tweet_number": leaf_node.tweet_number,
                    "content": leaf_node.tweet_content,
                    "title": leaf_node.title,
                    "node_idx": node_idx,
                    "leaf_idx": leaf_idx,
                    "section_title": node.title
                }
    
    if not target_tweet_info:
        raise ValueError(f"Tweet number {tweet_number} not found in the thread")
    
    # 获取总tweet数量
    total_tweets = len(all_tweets)
    
    # 步骤2：生成新tweet内容
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 设置生成模型
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_temperature = get_config_value(configurable.writer_temperature)
    
    # 初始化模型
    writer_model = init_chat_model(
        model=writer_model_name, 
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs,
        temperature=writer_temperature
    )
    
    # 构建上下文信息
    context_info = []
    context_info.append(f"Thread Topic: {outline.topic}")
    context_info.append(f"Target Tweet Position: {target_tweet_info['tweet_number']}/{total_tweets}")
    context_info.append(f"Target Tweet Title: {target_tweet_info['title']}")
    context_info.append("")
    context_info.append("Complete Tweet Thread:")
    
    # 添加所有tweets到context中
    for tweet in all_tweets:
        # 标记要修改的tweet
        if tweet["tweet_number"] == tweet_number:
            context_info.append(f">>> Tweet {tweet['tweet_number']} (TO MODIFY) - {tweet['title']}: {tweet['content']}")
        else:
            context_info.append(f"Tweet {tweet['tweet_number']} - {tweet['title']}: {tweet['content']}")
        
        # 在每个tweet后添加空行，以便更清晰地分隔
        context_info.append("")
    
    # 构建提示词
    user_prompt = format_modify_single_tweet_prompt(
        context_info=chr(10).join(context_info),
        modification_prompt=modification_prompt
    )

    # 调用LLM生成新tweet
    response = await writer_model.ainvoke([
        SystemMessage(content=modify_single_tweet_system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    # 确保获取字符串内容
    if isinstance(response.content, str):
        new_tweet_content = response.content.strip()
    else:
        # 如果是列表，取第一个元素或连接所有字符串
        new_tweet_content = str(response.content).strip()
    
    # 步骤3：更新outline
    # 创建新的outline副本
    updated_outline = outline.model_copy(deep=True)
    
    # 找到并更新指定的tweet
    node_idx = target_tweet_info["node_idx"]
    leaf_idx = target_tweet_info["leaf_idx"]
    
    # 更新tweet内容，保持其他信息不变
    updated_outline.nodes[node_idx].leaf_nodes[leaf_idx].tweet_content = new_tweet_content
    
    return {
        "updated_tweet": new_tweet_content
    }


# 构建workflow graph
builder = StateGraph(
    ModifySingleTweetState,
    input=ModifySingleTweetInput,
    output=ModifySingleTweetOutput,
    config_schema=WorkflowConfiguration
)

# 添加唯一的节点
builder.add_node("modify_single_tweet", modify_single_tweet)

# 添加边：简单的线性流程
builder.add_edge(START, "modify_single_tweet")
builder.add_edge("modify_single_tweet", END)

# 编译graph
graph = builder.compile() 