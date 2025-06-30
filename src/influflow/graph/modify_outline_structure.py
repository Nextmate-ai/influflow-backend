"""
Outline结构修改Workflow

用于调整已生成的Twitter thread的outline结构：
直接把新旧outline和原始tweets发给大模型，让其智能处理：
1. 补充新outline中缺失的tweet content
2. 根据上下文关联（如cliffhanger）调整相关tweets
3. 保持整体连贯性和一致性
"""

import json
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from typing import Dict, List

from influflow.state import ModifyOutlineStructureState, Outline, OutlineNode, OutlineLeafNode
from influflow.configuration import WorkflowConfiguration
from influflow.utils import get_config_value
from influflow.prompt import modify_outline_structure_system_prompt, format_modify_outline_structure_prompt



async def modify_outline_structure(state: ModifyOutlineStructureState, config: RunnableConfig):
    """使用AI智能修改outline结构
    
    将新旧outline和原始tweets发给大模型，让其智能处理所有变化：
    - 补充新outline中缺失的内容
    - 调整相关tweets以保持连贯性
    - 处理cliffhanger等上下文依赖
    
    Args:
        state: 包含原始outline和新结构的状态
        config: 配置信息
        
    Returns:
        包含更新后完整outline的字典
    """
    # 处理original_outline数据类型：如果是字典则转换为Outline对象
    original_outline_data = state["original_outline"]
    if isinstance(original_outline_data, dict):
        original_outline = Outline.model_validate(original_outline_data)
    else:
        original_outline = original_outline_data
    
    # 处理new_outline_structure数据类型：如果是字典则转换为Outline对象
    new_outline_structure_data = state["new_outline_structure"]
    if isinstance(new_outline_structure_data, dict):
        new_outline_structure = Outline.model_validate(new_outline_structure_data)
    else:
        new_outline_structure = new_outline_structure_data
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 设置生成模型
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    
    # 初始化模型，使用结构化输出
    writer_model = init_chat_model(
        model=writer_model_name, 
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs
    ).with_structured_output(Outline)
    
    # 构建原始outline结构（不包含tweet number）
    original_tweets = {
        "topic": original_outline.topic,
        "nodes": []
    }
    for node in original_outline.nodes:
        node_data = {
            "title": node.title,
            "leaf_nodes": []
        }
        for leaf in node.leaf_nodes:
            leaf_data = {
                "title": leaf.title,
                "tweet_content": leaf.tweet_content
            }
            node_data["leaf_nodes"].append(leaf_data)
        original_tweets["nodes"].append(node_data)
    
    # 构建新outline结构（不包含tweet number）
    new_structure = {
        "topic": new_outline_structure.topic,
        "nodes": []
    }
    for node in new_outline_structure.nodes:
        node_data = {
            "title": node.title,
            "leaf_nodes": []
        }
        for leaf in node.leaf_nodes:
            leaf_data = {
                "title": leaf.title,
                "tweet_content": leaf.tweet_content if hasattr(leaf, 'tweet_content') and leaf.tweet_content else ""
            }
            node_data["leaf_nodes"].append(leaf_data)
        new_structure["nodes"].append(node_data)
    
    # 格式化原始tweets列表为JSON格式
    original_tweets_str = json.dumps(original_tweets, ensure_ascii=False, indent=2)
    
    # 格式化新outline结构为JSON格式
    new_structure_str = json.dumps(new_structure, ensure_ascii=False, indent=2)
    
    # 使用prompt模块中的提示词
    user_prompt = format_modify_outline_structure_prompt(
        topic=original_outline.topic,
        original_tweets=original_tweets_str,
        new_structure=new_structure_str
    )

    # 调用LLM生成完整的更新后outline，直接返回结构化的Outline对象
    updated_outline = await writer_model.ainvoke([
        SystemMessage(content=modify_outline_structure_system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return {
        "updated_outline": updated_outline,
        "outline_str": updated_outline.display_outline(),
        "tweet_thread": updated_outline.display_tweet_thread()
    }


# 构建workflow graph
builder = StateGraph(
    ModifyOutlineStructureState,
    config_schema=WorkflowConfiguration
)

# 添加单个节点
builder.add_node("modify_outline_structure", modify_outline_structure)

# 添加边
builder.add_edge(START, "modify_outline_structure")
builder.add_edge("modify_outline_structure", END)

# 编译graph
graph = builder.compile() 