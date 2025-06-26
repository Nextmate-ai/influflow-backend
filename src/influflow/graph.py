from typing import Literal, List
import uuid
import json

# Influflow工作流：Twitter Thread生成流程
# 1. generate_outline -> human_feedback_outline -> generate_tweet_thread
# 2. human_feedback_thread -> adjust_outline_and_regenerate (如果需要调整)
# 3. finalize_thread -> END

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from langgraph.constants import Send
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from influflow.state import (
    InfluflowStateInput,
    InfluflowStateOutput,
    InfluflowState,
    OutlineNode,
    Tweet,
    TweetThread,
    OutlineAdjustment,
    SearchQuery,
    Queries
)

from influflow.structured_output import (
    OutlineStructure,
    AdjustedOutlineStructure,
    BatchTweetOutput
)

from influflow.prompt import (
    outline_query_writer_instructions,
    outline_generator_instructions,
    outline_human_feedback_prompt,
    tweet_query_writer_instructions,
    tweet_writer_instructions,
    thread_feedback_prompt,
    batch_tweet_generation_instructions,
    outline_complement_instructions
)

from influflow.configuration import WorkflowConfiguration
from influflow.utils import (
    format_outline_display,
    generate_outline_mindmap,
    build_outline_hierarchy,
    convert_outline_output_to_nodes,
    convert_adjusted_outline_output_to_updates,
    format_tweet_thread,
    calculate_thread_stats,
    update_nodes_description_by_id,
    get_level3_nodes,
    get_all_nodes,
    get_config_value,
    get_search_params,
    select_and_execute_search,
    get_today_str,
    format_outline_display_titles_only,
    execute_position_based_adjustments
)

## 主要节点实现 ##

async def generate_outline(state: InfluflowState, config: RunnableConfig):
    """
    生成Twitter thread的思维导图大纲
    
    这个节点：
    1. 根据主题生成搜索查询
    2. 执行网络搜索获取相关内容
    3. 使用LLM生成结构化的三层大纲
    """
    
    # 获取输入
    topic = state["topic"]
    feedback = state.get("feedback_on_outline", "")
    existing_context = state.get("outline_context", "")
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    number_of_queries = configurable.number_of_queries
    search_api = get_config_value(configurable.search_api)
    search_api_config = configurable.search_api_config or {}
    params_to_pass = get_search_params(search_api, search_api_config)

   # 设置大纲生成模型
    planner_provider = get_config_value(configurable.planner_provider)
    planner_model_name = get_config_value(configurable.planner_model)
    planner_model_kwargs = get_config_value(configurable.planner_model_kwargs or {})
    
    planner_model = init_chat_model(
        model=planner_model_name,
        model_provider=planner_provider,
        model_kwargs=planner_model_kwargs
    )
    
    # 如果没有搜索上下文，进行搜索
    need_search = existing_context == ""
    if need_search:
        # 生成搜索查询
        structured_llm = planner_model.with_structured_output(Queries)
        system_instructions_query = outline_query_writer_instructions.format(
            topic=topic,
            number_of_queries=number_of_queries,
            today=get_today_str()
        )
        
        queries_result = await structured_llm.ainvoke([
            SystemMessage(content=system_instructions_query),
            HumanMessage(content="Generate search queries for creating a comprehensive Twitter thread outline.")
        ])
        
        # 执行网络搜索
        query_list = [query.search_query for query in queries_result.queries]
        search_context = await select_and_execute_search(search_api, query_list, params_to_pass)
    else:
        search_context = existing_context
    
    # 格式化现有大纲结构（如果有的话）
    existing_outline_display = ""
    existing_nodes = state.get('outline_nodes', [])
    if existing_nodes:
        existing_outline_display = format_outline_display(existing_nodes)

    
    # 格式化系统指令
    system_instructions = outline_generator_instructions.format(
        topic=topic,
        feedback=feedback,
        outline_structure=existing_outline_display,
        thread_structure=configurable.thread_structure
    )
    
    # 格式化人类消息，包含搜索上下文
    human_message_content = f"""Generate a structured outline for a Twitter thread that will be engaging and shareable.

Search Context:
{search_context}"""
    
    # 使用导入的OutlineStructure类
    
    # 生成大纲
    structured_llm = planner_model.with_structured_output(OutlineStructure)
    outline_result = await structured_llm.ainvoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content=human_message_content)
    ])
    
    # 转换为OutlineNode对象（从outline_result.nodes获取递归结构）
    hierarchical_nodes = convert_outline_output_to_nodes(outline_result.nodes)
    
    return {
        "outline_nodes": hierarchical_nodes,
        "outline_context": search_context,
        "current_phase": "outline_generation"
    }

def human_feedback_outline(state: InfluflowState, config: RunnableConfig) -> Command[Literal["complement_outline_after_adjustment", "generate_tweet_thread"]]:
    """
    获取用户对大纲的反馈并支持JSON格式的调整操作
    """
    
    # 获取大纲节点和主题
    topic = state["topic"]
    outline_nodes = state['outline_nodes']
    
    # 格式化大纲显示
    outline_display = format_outline_display(outline_nodes)
    
    # 生成思维导图
    mindmap = generate_outline_mindmap(outline_nodes, topic)
    
    # 格式化用户提示
    user_prompt = outline_human_feedback_prompt.format(
        topic=topic,
        outline_display=f"{outline_display}\n\n{mindmap}"
    )
    
    # 获取用户反馈
    feedback = interrupt(user_prompt)
    
    # 如果用户批准大纲，开始生成tweet thread
    if isinstance(feedback, bool) and feedback is True:
        return Command(
            goto="generate_tweet_thread",
            update={"current_phase": "thread_generation"}
        )
    
    # 如果用户提供JSON调整，处理调整并补充信息
    else:
        try:
            # 解析用户输入的调整指令
            if isinstance(feedback, str):
                adjustments_data = json.loads(feedback)
            else:
                adjustments_data = feedback
            
            # 如果是单个调整，包装成列表
            if isinstance(adjustments_data, dict):
                adjustments_data = [adjustments_data]
            
            # 转换为基于位置的调整指令
            simplified_adjustments = []
            for adj_data in adjustments_data:
                if adj_data.get("action") in ["add", "delete", "modify"]:
                    simplified_adjustments.append(OutlineAdjustment(
                        action=adj_data["action"],
                        position=adj_data.get("position", "1"),  # 默认位置
                        new_title=adj_data.get("title", "New Node")
                    ))
            
            # 执行调整
            modified_nodes = execute_position_based_adjustments(outline_nodes, simplified_adjustments)
            
            return Command(
                goto="complement_outline_after_adjustment",
                update={
                    "outline_nodes": modified_nodes,
                    "current_phase": "outline_adjustment"
                }
            )
            
        except (json.JSONDecodeError, Exception) as e:
            # 如果解析失败，返回到当前节点重新输入
            return Command(
                goto="human_feedback_outline",
                update={"adjustment_error": f"Invalid input format: {str(e)}"}
            )



async def complement_outline_after_adjustment(state: InfluflowState, config: RunnableConfig):
    """
    用户调整大纲后，补充缺失的描述信息
    
    这个节点：
    1. 获取用户调整后的大纲结构（只有标题）
    2. 使用LLM为缺失描述的节点补充详细信息
    3. 保持用户提供的标题不变
    """
    
    # 获取输入
    topic = state["topic"]
    outline_nodes = state["outline_nodes"]
    existing_context = state.get("outline_context", "")
    
    # 检查是否需要补充信息（描述为空或太短）
    def check_needs_complement(nodes):
        for node in nodes:
            if not node.description.strip() or len(node.description) < 10 or node.status == "pending":
                return True
            if node.children and check_needs_complement(node.children):
                return True
        return False
    
    needs_complement = check_needs_complement(outline_nodes)
    if not needs_complement:
        # 如果不需要补充，直接生成tweets
        return Command(
            goto="generate_tweet_thread",
            update={"current_phase": "thread_generation"}
        )
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 格式化用户调整后的大纲结构（只显示标题）
    user_outline_display = format_outline_display_titles_only(outline_nodes)
    
    # 设置补充生成模型
    planner_provider = get_config_value(configurable.planner_provider)
    planner_model_name = get_config_value(configurable.planner_model)
    planner_model_kwargs = get_config_value(configurable.planner_model_kwargs or {})
    
    planner_model = init_chat_model(
        model=planner_model_name,
        model_provider=planner_provider,
        model_kwargs=planner_model_kwargs
    )
    
    # 格式化补充指令
    system_instructions = outline_complement_instructions.format(
        topic=topic,
        user_outline_structure=user_outline_display,
        search_context=existing_context
    )
    
    # 使用AdjustedOutlineStructure来补充信息
    
    structured_llm = planner_model.with_structured_output(AdjustedOutlineStructure)
    complement_result = await structured_llm.ainvoke([
        SystemMessage(content=system_instructions),
        HumanMessage(content="Complement the user's outline structure with detailed descriptions while keeping all titles exactly as provided.")
    ])
    
    # 转换为更新信息列表（从complement_result.nodes获取递归结构）
    update_info_list = convert_adjusted_outline_output_to_updates(complement_result.nodes)
    
    # 批量更新节点描述
    _ = update_nodes_description_by_id(outline_nodes, update_info_list)
    
    # 更新成功后，直接进入tweet生成阶段
    return {
        "outline_nodes": outline_nodes,
        "outline_context": existing_context,
        "current_phase": "thread_generation"
    }

async def generate_tweet_thread(state: InfluflowState, config: RunnableConfig):
    """
    为大纲的所有节点生成完整的tweet thread
    
    这个节点：
    1. 收集所有需要生成tweet的节点（每个节点对应一个tweet）
    2. 统一搜索相关内容（如果需要）
    3. 一次性生成所有tweets，确保连贯性
    """
    
    # 使用导入的BatchTweetOutput类
    
    # 获取所有节点（每个节点都需要生成tweet）
    topic = state["topic"]
    outline_nodes = state["outline_nodes"]
    search_context = state["outline_context"]
    all_nodes = get_all_nodes(outline_nodes)
    
    if not all_nodes:
        # 如果没有节点，返回空thread
        empty_thread = TweetThread(
            id=str(uuid.uuid4()),
            topic=topic,
            tweets=[],
            total_tweets=0
        )
        return {
            "tweet_thread": empty_thread,
            "current_phase": "thread_generation"
        }
    
    # 获取配置
    configurable = WorkflowConfiguration.from_runnable_config(config)
    
    # 准备大纲内容描述
    outline_content = ""
    for i, node in enumerate(all_nodes, 1):
        outline_content += f"{i}. {node.title}: {node.description}\n"
    
    # 设置tweet生成模型
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    tweet_writer = init_chat_model(
        model=writer_model_name,
        model_provider=writer_provider,
        model_kwargs=writer_model_kwargs
    )
    
    # 格式化批量生成指令
    batch_instructions = batch_tweet_generation_instructions.format(
        topic=topic,
        total_tweets=len(all_nodes),
        outline_content=outline_content
    )
    
    # 格式化人类消息，包含搜索上下文
    human_message_content = f"""Generate all {len(all_nodes)} tweets for this Twitter thread about '{topic}'. Make sure each tweet corresponds to the outline points and creates a cohesive, engaging thread.

Search Context:
{search_context}"""
    
    # 一次性生成所有tweets
    structured_llm = tweet_writer.with_structured_output(BatchTweetOutput)
    batch_result = await structured_llm.ainvoke([
        SystemMessage(content=batch_instructions),
        HumanMessage(content=human_message_content)
    ])
    
    # 转换为Tweet对象
    tweets = []
    for i, (tweet_output, node) in enumerate(zip(batch_result.tweets, all_nodes), 1):
        tweet = Tweet(
            id=str(uuid.uuid4()),
            content=tweet_output.content,
            outline_node_id=node.id,
            thread_position=i
        )
        tweets.append(tweet)
        
        # 更新节点状态为已完成
        node.status = "completed"
    
    # 创建TweetThread对象
    tweet_thread = TweetThread(
        id=str(uuid.uuid4()),
        topic=topic,
        tweets=tweets,
        total_tweets=len(tweets)
    )
    
    return {
        "tweet_thread": tweet_thread,
        "outline_nodes": outline_nodes,  # 更新节点状态
        "current_phase": "thread_generation"
    }

def human_feedback_thread(state: InfluflowState, config: RunnableConfig) -> Command[Literal["adjust_outline_and_regenerate", "finalize_thread"]]:
    """
    获取用户对tweet thread的反馈
    """
    
    tweet_thread = state["tweet_thread"]
    
    if not tweet_thread or not tweet_thread.tweets:
        return Command(goto="finalize_thread")
    
    # 格式化thread内容
    thread_content = format_tweet_thread(tweet_thread.tweets, tweet_thread.topic)
    
    # 计算统计信息
    stats = calculate_thread_stats(tweet_thread.tweets)
    
    # 格式化用户提示
    user_prompt = thread_feedback_prompt.format(
        thread_content=thread_content,
        total_tweets=stats["total_tweets"],
        estimated_time=stats["estimated_reading_time"],
        character_stats=f"Average: {stats['avg_characters']} chars/tweet, Usage: {stats['character_usage']}"
    )
    
    # 获取用户反馈
    feedback = interrupt(user_prompt)
    
    # 如果用户满意，进入最终确认
    if isinstance(feedback, bool) and feedback is True:
        return Command(
            goto="finalize_thread",
            update={"current_phase": "completed"}
        )
    
    # 如果用户提供反馈，进入调整阶段
    elif isinstance(feedback, str):
        return Command(
            goto="adjust_outline_and_regenerate",
            update={
                "feedback_on_thread": feedback,
                "current_phase": "thread_adjustment"
            }
        )
    else:
        raise TypeError(f"Interrupt value of type {type(feedback)} is not supported.")

async def adjust_outline_and_regenerate(state: InfluflowState, config: RunnableConfig) -> Command[Literal["adjust_outline_and_regenerate", "generate_tweet_thread", "finalize_thread"]]:
    """
    允许用户调整大纲并重新生成受影响的tweets
    """
    
    # 显示当前状态
    topic = state["topic"]
    outline_nodes = state["outline_nodes"]
    tweet_thread = state.get("tweet_thread")
    
    outline_display = format_outline_display(outline_nodes)
    
    # 显示当前thread预览
    thread_preview = ""
    if tweet_thread and tweet_thread.tweets:
        thread_preview = format_tweet_thread(tweet_thread.tweets[:3], topic)  # 只显示前3条
        if len(tweet_thread.tweets) > 3:
            thread_preview += f"\n... and {len(tweet_thread.tweets) - 3} more tweets"
    
    # 构建用户提示
    user_prompt = f"""Current Outline and Thread Status:

{outline_display}

Current Thread Preview:
{thread_preview}

You can adjust the outline structure using the following commands:

ADD a new item (inserts at the specified position):
{{"action": "add", "position": "2.1", "new_title": "New Title"}}

DELETE an item (removes the item at the specified position):
{{"action": "delete", "position": "1"}}

MODIFY an item (changes title, description will be auto-generated):
{{"action": "modify", "position": "2.1", "new_title": "Updated Title"}}

Position format examples:
- "1" = first main section
- "2.1" = first subsection of second main section  
- "3.2.1" = first tweet point of second subsection of third main section

You can provide multiple adjustments at once, or pass 'true' to approve the current thread.

What adjustments would you like to make?"""
    
    # 获取用户输入
    user_input = interrupt(user_prompt)
    
    # 如果用户选择完成
    if isinstance(user_input, bool) and user_input is True:
        return Command(goto="finalize_thread", update={"current_phase": "completed"})
    
    # 解析用户输入的调整指令
    try:
        if isinstance(user_input, str):
            adjustments_data = json.loads(user_input)
        else:
            adjustments_data = user_input
        
        # 如果是单个调整，包装成列表
        if isinstance(adjustments_data, dict):
            adjustments_data = [adjustments_data]
        
        adjustments = [OutlineAdjustment(**adj) for adj in adjustments_data]
    except (json.JSONDecodeError, Exception) as e:
        return Command(
            goto="adjust_outline_and_regenerate",
            update={"adjustment_error": f"Invalid input format: {str(e)}"}
        )
    
    # 执行基于位置的调整
    updated_outline_nodes = execute_position_based_adjustments(outline_nodes, adjustments)
    
    # 检查是否有修改（比较调整前后的节点数量或内容）
    has_modifications = len(updated_outline_nodes) != len(outline_nodes)
    
    # 如果有修改，重新生成受影响的tweets
    if has_modifications:
        return Command(
            goto="generate_tweet_thread",
            update={
                "outline_nodes": updated_outline_nodes,
                "current_phase": "thread_generation"
            }
        )
    else:
        # 没有修改，直接完成
        return Command(goto="finalize_thread", update={"current_phase": "completed"})

def finalize_thread(state: InfluflowState, config: RunnableConfig):
    """
    最终确认并格式化完整的tweet thread
    """
    
    tweet_thread = state.get("tweet_thread")
    outline_nodes = state.get("outline_nodes", [])
    
    if not tweet_thread or not tweet_thread.tweets:
        return {
            "final_tweet_thread": f"No tweet thread generated for topic: {state['topic']}",
            "outline_structure": format_outline_display(outline_nodes),
            "current_phase": "completed"
        }
    
    # 格式化最终的tweet thread
    final_thread_content = format_tweet_thread(tweet_thread.tweets, tweet_thread.topic)
    
    # 格式化大纲结构
    outline_structure = format_outline_display(outline_nodes)
    
    return {
        "final_tweet_thread": final_thread_content,
        "outline_structure": outline_structure,
        "current_phase": "completed"
    }

# 构建图结构
builder = StateGraph(
    InfluflowState, 
    input=InfluflowStateInput, 
    output=InfluflowStateOutput, 
    config_schema=WorkflowConfiguration
)

# 添加节点
builder.add_node("generate_outline", generate_outline)
builder.add_node("human_feedback_outline", human_feedback_outline)
builder.add_node("complement_outline_after_adjustment", complement_outline_after_adjustment)
builder.add_node("generate_tweet_thread", generate_tweet_thread)
builder.add_node("human_feedback_thread", human_feedback_thread)
builder.add_node("adjust_outline_and_regenerate", adjust_outline_and_regenerate)
builder.add_node("finalize_thread", finalize_thread)

# 添加边
builder.add_edge(START, "generate_outline")
builder.add_edge("generate_outline", "human_feedback_outline")
builder.add_edge("complement_outline_after_adjustment", "generate_tweet_thread")
# builder.add_edge("generate_tweet_thread", "human_feedback_thread")
builder.add_edge("generate_tweet_thread", END)
builder.add_edge("finalize_thread", END)

# 编译图
graph = builder.compile()
