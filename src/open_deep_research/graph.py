from typing import Literal
import uuid

# 简化的报告生成工作流：
# 1. generate_report_plan -> human_feedback -> build_section_with_web_research (并行)
# 2. gather_completed_sections -> write_final_sections -> compile_final_report
# 3. adjust_sections (人工介入) -> 回到human_feedback重新构建整个报告
# 
# Section调整功能支持：
# 1. 增加section - 添加新的section到指定位置
# 2. 删除section - 删除指定的section
# 3. 修改section - 修改section描述并重新生成内容
# 
# 调整指令格式：
# 增加: {"action": "add", "section_path": "2", "new_section": {...}}
# 删除: {"action": "delete", "section_path": "1.2"}  
# 修改: {"action": "modify", "section_path": "3", "modification_prompt": "请添加更多技术细节"}
#
# 支持多轮调整，直到用户明确完成报告

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from langgraph.constants import Send
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from open_deep_research.state import (
    ReportStateInput,
    ReportStateOutput,
    Sections,
    SectionsPlan,
    ReportState,
    SectionState,
    SectionOutputState,
    Queries,
    Feedback,
    Section,
    SectionPlan,
    SectionContent,
    SectionAdjustment,
    convert_sections_plan_to_sections,
    convert_section_plan_to_section
)

from open_deep_research.prompts import (
    report_planner_query_writer_instructions,
    report_planner_instructions,
    report_planner_human_prompt,
    query_writer_instructions, 
    section_writer_instructions,
    final_section_writer_instructions,
    section_grader_instructions,
    section_writer_inputs
)

from open_deep_research.configuration import WorkflowConfiguration
from open_deep_research.utils import (
    format_sections, 
    get_config_value, 
    get_search_params, 
    select_and_execute_search,
    get_today_str,
    generate_mindmap
)

## Nodes -- 

async def generate_report_plan(state: ReportState, config: RunnableConfig):
    """Generate the initial report plan with sections.
    
    This node:
    1. Gets configuration for the report structure and search parameters
    2. Generates search queries to gather context for planning
    3. Performs web searches using those queries
    4. Uses an LLM to generate a structured plan with sections
    
    Args:
        state: Current graph state containing the report topic
        config: Configuration for models, search APIs, etc.
        
    Returns:
        Dict containing the generated sections
    """

    # Inputs
    topic = state["topic"]

    # Get local sources
    local_sources = state.get("local_sources", [])
    if local_sources:
        formatted_sources = []
        for i, source in enumerate(local_sources, 1):
            formatted_sources.append(f"----Local Source [{i}] -------\n{source}")
        local_sources_str = "\n\n".join(formatted_sources)
    else:
        local_sources_str = ""

    # Get feedback on the report plan (single latest feedback)
    feedback = state.get("feedback_on_report_plan", "")

    # Get context of the report plan
    report_plan_context = state.get("report_plan_context", "")
    need_web_search = report_plan_context == ""

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)
    report_structure = configurable.report_structure
    number_of_queries = configurable.number_of_queries
    search_api = get_config_value(configurable.search_api)
    search_api_config = configurable.search_api_config or {}  # Get the config dict, default to empty
    params_to_pass = get_search_params(search_api, search_api_config)  # Filter parameters

    # Convert JSON object to string if necessary
    if isinstance(report_structure, dict):
        report_structure = str(report_structure)

    # Set writer model (model used for query writing)
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider, model_kwargs=writer_model_kwargs) 
    structured_llm = writer_model.with_structured_output(Queries)

    if need_web_search:
        # Format system instructions
        system_instructions_query = report_planner_query_writer_instructions.format(
            topic=topic,
            report_organization=report_structure,
            number_of_queries=number_of_queries,
            today=get_today_str()
        )

        # Generate queries  
        results = await structured_llm.ainvoke([SystemMessage(content=system_instructions_query),
                                        HumanMessage(content="Generate search queries that will help with planning the sections of the report.")])

        # Web search
        query_list = [query.search_query for query in results.queries]

        # Search the web with parameters
        source_str = await select_and_execute_search(search_api, query_list, params_to_pass)
        report_plan_context = source_str
    else:
        source_str = report_plan_context

    # Format sections - 安全地获取现有的sections（如果存在的话）
    def format_existing_sections(sections: list[Section], level: int = 0) -> str:
        """递归格式化现有章节"""
        sections_str = ""
        indent = "  " * level
        
        for section in sections:
            sections_str += f"{indent}Section: {section.name}\n"
            sections_str += f"{indent}Description: {section.description}\n"
            sections_str += f"{indent}Research needed: {'Yes' if section.research else 'No'}\n"
            
            # 递归处理子章节
            if section.sections:
                sections_str += f"{indent}Subsections:\n"
                sections_str += format_existing_sections(section.sections, level + 1)
            
            sections_str += "\n"
        
        return sections_str
    
    sections_str = ""
    existing_sections = state.get('sections', [])
    if existing_sections:
        sections_str = format_existing_sections(existing_sections)

    # Format system instructions
    system_instructions_sections = report_planner_instructions.format(topic=topic, report_organization=report_structure, feedback=feedback, sections=sections_str)

    # Set the planner
    planner_provider = get_config_value(configurable.planner_provider)
    planner_model = get_config_value(configurable.planner_model)
    planner_model_kwargs = get_config_value(configurable.planner_model_kwargs or {})

    # Report planner instructions
    planner_message = report_planner_human_prompt.format(online_sources=source_str, local_sources=local_sources_str)

    # Run the planner
    if planner_model == "claude-3-7-sonnet-latest":
        # Allocate a thinking budget for claude-3-7-sonnet-latest as the planner model
        planner_llm = init_chat_model(model=planner_model, 
                                      model_provider=planner_provider, 
                                      max_tokens=20_000, 
                                      thinking={"type": "enabled", "budget_tokens": 16_000})

    else:
        # With other models, thinking tokens are not specifically allocated
        planner_llm = init_chat_model(model=planner_model, 
                                      model_provider=planner_provider,
                                      model_kwargs=planner_model_kwargs)
    
    # Generate the report sections
    structured_llm = planner_llm.with_structured_output(SectionsPlan)
    report_sections_plan = await structured_llm.ainvoke([SystemMessage(content=system_instructions_sections),
                                             HumanMessage(content=planner_message)])

    # 将SectionsPlan转换为Section列表（添加内部管理字段）
    sections = convert_sections_plan_to_sections(report_sections_plan)

    return {"sections": sections, "report_plan_context": report_plan_context, "local_sources_str": local_sources_str}

def human_feedback(state: ReportState, config: RunnableConfig) -> Command[Literal["generate_report_plan","build_section_with_web_research"]]:
    """Get human feedback on the report plan and route to next steps.
    
    This node:
    1. Formats the current hierarchical report plan for human review
    2. Gets feedback via an interrupt
    3. Routes to either:
       - Section writing if plan is approved
       - Plan regeneration if feedback is provided
    
    Args:
        state: Current graph state with sections to review
        config: Configuration for the workflow
        
    Returns:
        Command to either regenerate plan or start section writing
    """

    def format_section_hierarchy(section: Section, level: int = 0) -> str:
        """递归格式化章节层次结构"""
        indent = "  " * level
        section_str = f"{indent}Section: {section.name}\n"
        section_str += f"{indent}Description: {section.description}\n"
        section_str += f"{indent}Research needed: {'Yes' if section.research else 'No'}\n"
        section_str += f"{indent}Status: {section.status}\n"
        
        # 递归处理子章节
        if section.sections:
            section_str += f"{indent}Subsections:\n"
            for subsection in section.sections:
                section_str += format_section_hierarchy(subsection, level + 1)
        
        return section_str + "\n"
    
    def collect_research_sections(sections: list[Section]) -> list[Section]:
        """递归收集所有需要研究且状态为pending的章节（包括子章节）"""
        research_sections = []
        
        for section in sections:
            # 如果当前章节需要研究且状态为pending，添加到列表
            if section.research and section.status == "pending":
                section.status = "in_progress"  # 标记为进行中
                research_sections.append(section)
            
            # 递归处理子章节
            if section.sections:
                research_sections.extend(collect_research_sections(section.sections))
        
        return research_sections

    # Get sections
    topic = state["topic"]
    sections = state['sections']
    
    # 格式化层次结构的章节显示
    sections_str = ""
    for section in sections:
        sections_str += format_section_hierarchy(section)

    # Get feedback on the report plan from interrupt
    interrupt_message = f"""Please provide feedback on the following hierarchical report plan. 
                        \n\n{sections_str}
                        \n\n{generate_mindmap(sections)}\n
                        \nDoes the report plan meet your needs?\nPass 'true' to approve the report plan.\nOr, provide feedback to regenerate the report plan:"""
    
    feedback = interrupt(interrupt_message)

    # If the user approves the report plan, kick off section writing
    if isinstance(feedback, bool) and feedback is True:
        # 收集所有需要研究的章节（包括子章节）
        research_sections = collect_research_sections(sections)
        
        # Get local_sources_str from state
        local_sources_str = state.get("local_sources_str", "")
        
        # Treat this as approve and kick off section writing
        return Command(
            goto=[
                Send("build_section_with_web_research", {"topic": topic, "section": s, "search_iterations": 0, "local_sources_str": local_sources_str}) 
                for s in research_sections
            ],
            update={"sections": sections}  # 更新sections状态
        )
    
    # If the user provides feedback, regenerate the report plan 
    elif isinstance(feedback, str):
        # Treat this as feedback and append it to the existing list
        return Command(goto="generate_report_plan", 
                       update={"feedback_on_report_plan": feedback})
    else:
        raise TypeError(f"Interrupt value of type {type(feedback)} is not supported.")
    
async def generate_queries(state: SectionState, config: RunnableConfig):
    """Generate search queries for researching a specific section.
    
    This node uses an LLM to generate targeted search queries based on the 
    section topic and description.
    
    Args:
        state: Current state containing section details
        config: Configuration including number of queries to generate
        
    Returns:
        Dict containing the generated search queries
    """

    # Get state 
    topic = state["topic"]
    section = state["section"]

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)
    number_of_queries = configurable.number_of_queries

    # Generate queries 
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider, model_kwargs=writer_model_kwargs) 
    structured_llm = writer_model.with_structured_output(Queries)

    # Format system instructions
    system_instructions = query_writer_instructions.format(topic=topic, 
                                                           section_topic=section.description, 
                                                           number_of_queries=number_of_queries,
                                                           today=get_today_str())

    # Generate queries  
    queries = await structured_llm.ainvoke([SystemMessage(content=system_instructions),
                                     HumanMessage(content="Generate search queries on the provided topic.")])

    return {"search_queries": queries.queries}

async def search_web(state: SectionState, config: RunnableConfig):
    """Execute web searches for the section queries.
    
    This node:
    1. Takes the generated queries
    2. Executes searches using configured search API
    3. Formats results into usable context
    
    Args:
        state: Current state with search queries
        config: Search API configuration
        
    Returns:
        Dict with search results and updated iteration count
    """

    # Get state
    search_queries = state["search_queries"]

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)
    search_api = get_config_value(configurable.search_api)
    search_api_config = configurable.search_api_config or {}  # Get the config dict, default to empty
    params_to_pass = get_search_params(search_api, search_api_config)  # Filter parameters

    # Web search
    query_list = [query.search_query for query in search_queries]

    # Search the web with parameters
    source_str = await select_and_execute_search(search_api, query_list, params_to_pass)

    return {"source_str": source_str, "search_iterations": state["search_iterations"] + 1}

async def write_section(state: SectionState, config: RunnableConfig) -> Command[Literal[END, "search_web"]]:
    """Write a section of the report and evaluate if more research is needed.
    
    This node:
    1. Writes section content using search results
    2. Evaluates the quality of the section
    3. Either:
       - Completes the section if quality passes
       - Triggers more research if quality fails
    
    Args:
        state: Current state with search results and section info
        config: Configuration for writing and evaluation
        
    Returns:
        Command to either complete section or do more research
    """

    # Get state 
    topic = state["topic"]
    section = state["section"]
    source_str = state["source_str"]
    local_sources_str = state["local_sources_str"]

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)

    # Format system instructions
    section_writer_inputs_formatted = section_writer_inputs.format(topic=topic, 
                                                             section_name=section.name, 
                                                             section_topic=section.description, 
                                                             online_sources=source_str, 
                                                             local_sources=local_sources_str, 
                                                             section_content=section.content)

    # Generate section  
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider, model_kwargs=writer_model_kwargs).with_structured_output(SectionContent)

    section_content = await writer_model.ainvoke([SystemMessage(content=section_writer_instructions),
                                           HumanMessage(content=section_writer_inputs_formatted)])
    
    # Write content to the section object  
    section.content = section_content.content
    section.sources = section_content.sources

    # 如果最大搜索深度小于2，跳过质量评分直接完成章节
    if configurable.max_search_depth < 2:
        # 标记章节为已完成
        section.status = "completed"
        # 构建输出状态，符合SectionOutputState格式
        output = {"completed_section": [section]}
        if configurable.include_source_str:
            output["source_str"] = source_str
        return Command(update=output, goto=END)

    # Grade prompt 
    section_grader_message = ("Grade the report and consider follow-up questions for missing information. "
                              "If the grade is 'pass', return empty strings for all follow-up queries. "
                              "If the grade is 'fail', provide specific search queries to gather missing information.")
    
    section_grader_instructions_formatted = section_grader_instructions.format(topic=topic, 
                                                                               section_topic=section.description,
                                                                               section=section.content, 
                                                                               number_of_follow_up_queries=configurable.number_of_queries)

    # Use planner model for reflection
    planner_provider = get_config_value(configurable.planner_provider)
    planner_model = get_config_value(configurable.planner_model)
    planner_model_kwargs = get_config_value(configurable.planner_model_kwargs or {})

    if planner_model == "claude-3-7-sonnet-latest":
        # Allocate a thinking budget for claude-3-7-sonnet-latest as the planner model
        reflection_model = init_chat_model(model=planner_model, 
                                           model_provider=planner_provider, 
                                           max_tokens=20_000, 
                                           thinking={"type": "enabled", "budget_tokens": 16_000}).with_structured_output(Feedback)
    else:
        reflection_model = init_chat_model(model=planner_model, 
                                           model_provider=planner_provider, model_kwargs=planner_model_kwargs).with_structured_output(Feedback)
    # Generate feedback
    feedback = await reflection_model.ainvoke([SystemMessage(content=section_grader_instructions_formatted),
                                        HumanMessage(content=section_grader_message)])

    # If the section is passing or the max search depth is reached, mark section as completed
    if feedback.grade == "pass" or state["search_iterations"] >= configurable.max_search_depth:
        # 标记章节为已完成
        section.status = "completed"
        # 构建输出状态，符合SectionOutputState格式
        output = {"completed_section": [section]}
        if configurable.include_source_str:
            output["source_str"] = source_str
        return Command(update=output, goto=END)

    # Update the existing section with new content and update search queries
    else:
        return Command(
            update={"search_queries": feedback.follow_up_queries, "section": section},
            goto="search_web"
        )
    
async def write_final_sections(state: SectionState, config: RunnableConfig):
    """Write sections that don't require research using completed sections as context.
    
    This node handles sections like conclusions or summaries that build on
    the researched sections rather than requiring direct research.
    For hierarchical structures, parent sections will use their subsections as context.
    
    Args:
        state: Current state with completed sections as context
        config: Configuration for the writing model
        
    Returns:
        Dict containing the newly written section with status updated
    """

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)

    # Get state 
    topic = state["topic"]
    section = state["section"]
    completed_report_sections = state["report_sections_from_research"]
    
    # 检查是否是父章节（有子章节的章节）
    is_parent_section = section.sections is not None and len(section.sections) > 0
    
    if is_parent_section:
        # 父章节：基于其子章节的内容生成概述
        # 收集所有子章节的内容作为上下文
        subsection_content = ""
        def collect_subsection_content(sections: list[Section], level: int = 1) -> str:
            content = ""
            for subsec in sections:
                if subsec.content:
                    indent = "  " * level
                    content += f"{indent}## {subsec.name}\n{indent}{subsec.content}\n\n"
                # 递归收集子子章节的内容
                if subsec.sections:
                    content += collect_subsection_content(subsec.sections, level + 1)
            return content
        
        subsection_content = collect_subsection_content(section.sections)
        
        # 使用子章节内容作为主要上下文，已完成的研究章节作为补充上下文
        context = f"Subsections content:\n{subsection_content}"
    else:
        # 叶子章节：使用所有已完成的研究章节作为上下文
        context = completed_report_sections
    
    # Format system instructions
    system_instructions = final_section_writer_instructions.format(
        topic=topic, 
        section_name=section.name, 
        section_topic=section.description, 
        context=context
    )

    # Generate section  
    writer_provider = get_config_value(configurable.writer_provider)
    writer_model_name = get_config_value(configurable.writer_model)
    writer_model_kwargs = get_config_value(configurable.writer_model_kwargs or {})
    writer_model = init_chat_model(model=writer_model_name, model_provider=writer_provider, model_kwargs=writer_model_kwargs) 
    
    section_content = await writer_model.ainvoke([SystemMessage(content=system_instructions),
                                           HumanMessage(content="Generate a report section based on the provided sources.")])
    
    # Write content to section and mark as completed
    section.content = section_content.content
    section.status = "completed"

    # 明确返回更新后的section对象以确保状态同步，符合SectionOutputState格式
    return {"completed_section": [section]}

def gather_completed_sections(state: ReportState):
    """Format completed sections as context for writing final sections.
    
    This node takes all completed research sections from the unified section structure
    and formats them into a single context string for writing summary sections.
    Also handles merging updated section objects from subgraphs back into the main structure.
    
    Args:
        state: Current state with sections containing completion status and possibly 
               updated section objects from completed subgraphs
        
    Returns:
        Dict with updated sections structure and formatted sections as context
    """
    
    def update_section_in_structure(sections: list[Section], updated_section: Section) -> list[Section]:
        """递归查找并更新对应的section对象"""
        for i, section in enumerate(sections):
            if section.id == updated_section.id:
                sections[i] = updated_section
                return sections
            # 递归查找子章节
            if section.sections:
                section.sections = update_section_in_structure(section.sections, updated_section)
        return sections

    def collect_completed_sections(sections: list[Section]) -> list[Section]:
        """递归收集所有已完成的章节"""
        completed = []
        for section in sections:
            if section.status == "completed":
                completed.append(section)
            # 递归处理子章节
            if section.sections:
                completed.extend(collect_completed_sections(section.sections))
        return completed

    # 从原始sections开始
    sections = state["sections"].copy() if state["sections"] else []
    
    # 处理从section subgraphs返回的更新后的section对象
    # LangGraph会将并行subgraph的返回结果合并到state中
    if "completed_section" in state:
        completed_sections_from_subgraphs = state["completed_section"]
        # completed_section 由于使用了 operator.add 已经是一个展平的 Section 列表
        # 直接更新到主结构中
        for updated_section in completed_sections_from_subgraphs:
            sections = update_section_in_structure(sections, updated_section)

    # 收集已完成的章节
    completed_sections = collect_completed_sections(sections)

    # Format completed section to str to use as context for final sections
    completed_report_sections = format_sections(completed_sections)

    # 返回更新后的sections结构和格式化的已完成章节内容
    return {
        "sections": sections,  # 更新后的sections结构
        "report_sections_from_research": completed_report_sections
    }

def compile_final_report(state: ReportState, config: RunnableConfig):
    """Compile all sections into the final report with hierarchical structure.
    
    This node:
    1. Gets all sections with their completion status
    2. Compiles them into the final report with proper hierarchy
    3. Only includes content from completed sections
    
    Args:
        state: Current state with all sections and their status
        config: Configuration for the workflow
        
    Returns:
        Dict containing the complete report
    """

    def compile_section_content(section: Section, level: int = 1) -> str:
        """递归编译章节内容为最终报告格式，只包含已完成的章节"""
        # 根据层级确定标题格式
        if level == 1:
            header = "#"  # H1 for top level
        elif level == 2:
            header = "##"  # H2 for second level
        else:
            header = "###"  # H3 for third level
        
        # 构建当前章节内容（只有已完成的章节才有内容）
        section_content = ""
        if section.status == "completed" and section.content:
            section_content = f"{header} {section.name}\n\n{section.content}\n\n"
        
        # 递归编译子章节
        if section.sections:
            for subsection in section.sections:
                section_content += compile_section_content(subsection, level + 1)
        
        return section_content

    # Get configuration
    configurable = WorkflowConfiguration.from_runnable_config(config)

    # Get sections
    sections = state["sections"]

    # Compile final report with hierarchical structure
    final_report = ""
    for section in sections:
        final_report += compile_section_content(section)

    # Remove trailing whitespace
    final_report = final_report.strip()

    if configurable.include_source_str:
        return {"final_report": final_report, "source_str": state["source_str"]}
    else:
        return {"final_report": final_report}



def parse_section_path(path: str) -> list[int]:
    """解析section路径字符串为索引列表"""
    try:
        return [int(x) - 1 for x in path.split('.') if x.strip()]  # 转换为0-based索引
    except ValueError:
        raise ValueError(f"Invalid section path format: {path}")

def find_section_by_path(sections: list[Section], path: str) -> tuple[Section, list[Section], int]:
    """根据路径查找section，返回(目标section, 父容器列表, 在父容器中的索引)"""
    indices = parse_section_path(path)
    if not indices:
        raise ValueError("Empty section path")
    
    current_sections = sections
    parent_sections = None
    parent_index = -1
    
    for i, index in enumerate(indices):
        if index >= len(current_sections):
            raise IndexError(f"Section index {index + 1} out of range at level {i + 1}")
        
        if i == len(indices) - 1:  # 最后一级
            parent_sections = current_sections
            parent_index = index
            return current_sections[index], parent_sections, parent_index
        else:
            current_sections = current_sections[index].sections or []
    
    raise ValueError("Invalid path")

def add_section_at_path(sections: list[Section], path: str, new_section: Section) -> list[Section]:
    """在指定路径添加section"""
    indices = parse_section_path(path)
    if not indices:
        # 添加到顶级
        sections.append(new_section)
        return sections
    
    if len(indices) == 1:
        # 添加到顶级的指定位置
        index = indices[0]
        if index > len(sections):
            index = len(sections)  # 如果索引超出范围，添加到末尾
        sections.insert(index, new_section)
        return sections
    
    # 添加到子级
    parent_path = '.'.join(str(i + 1) for i in indices[:-1])
    target_section, _, _ = find_section_by_path(sections, parent_path)
    
    if target_section.sections is None:
        target_section.sections = []
    
    child_index = indices[-1]
    if child_index > len(target_section.sections):
        child_index = len(target_section.sections)
    
    target_section.sections.insert(child_index, new_section)
    return sections

def delete_section_at_path(sections: list[Section], path: str) -> list[Section]:
    """删除指定路径的section"""
    _, parent_sections, parent_index = find_section_by_path(sections, path)
    if parent_sections is not None and 0 <= parent_index < len(parent_sections):
        parent_sections.pop(parent_index)
    return sections



def format_sections_for_display(sections: list[Section], level: int = 0, parent_path: str = "") -> str:
    """格式化sections用于显示给用户"""
    result = ""
    for i, section in enumerate(sections, 1):
        indent = "  " * level
        # 构建当前路径
        if parent_path:
            current_path = f"{parent_path}.{i}"
        else:
            current_path = str(i)
            
        result += f"{indent}{current_path}. {section.name}\n"
        result += f"{indent}   Description: {section.description}\n"
        result += f"{indent}   Research needed: {'Yes' if section.research else 'No'}\n"
        result += f"{indent}   Status: {section.status}\n"
        if section.content:
            content_preview = section.content[:100] + "..." if len(section.content) > 100 else section.content
            result += f"{indent}   Content preview: {content_preview}\n"
        
        if section.sections:
            result += format_sections_for_display(section.sections, level + 1, current_path)
        result += "\n"
    
    return result

def gather_sections_router(state: ReportState):
    """简化路由：直接检查是否有需要写的final sections"""
    def collect_non_research_sections(sections: list[Section]) -> list[Section]:
        result = []
        for section in sections:
            if not section.research and section.status != "completed":
                result.append(section)
            if section.sections:
                result.extend(collect_non_research_sections(section.sections))
        return result
    
    non_research_sections = collect_non_research_sections(state["sections"])
    
    if non_research_sections:
        # 返回Send列表以并行处理所有final sections
        return [
            Send("write_final_sections", {
                "topic": state["topic"], 
                "section": s, 
                "report_sections_from_research": state["report_sections_from_research"]
            }) for s in non_research_sections
        ]
    else:
        return "compile_final_report"



async def adjust_sections(state: ReportState, config: RunnableConfig) -> Command[Literal["adjust_sections", "process_adjustment_research", "compile_final_report", END]]:
    """允许用户调整sections（增加/删除/修改）并只重新生成需要调整的部分"""

    # 显示当前的sections结构
    sections_display = format_sections_for_display(state["sections"])
    
    # 显示当前报告的前500字符作为预览
    final_report = state["final_report"]
    report_preview = final_report[:500] + "..." if len(final_report) > 500 else final_report
    
    # 构建用户提示
    user_prompt = f"""Current Report Structure:
{sections_display}

Current Report Preview:
{report_preview}

You can now adjust the report sections. Please provide your adjustments in the following format:

For adding a section:
{{
    "action": "add",
    "section_path": "2",
    "section_name": "Section Name"
}}

For deleting a section:
{{
    "action": "delete", 
    "section_path": "1.3"
}}

For modifying a section:
{{
    "action": "modify",
    "section_path": "2",
    "modification_prompt": "How to modify this section..."
}}

You can provide multiple adjustments at once. Or pass 'true' to finish and complete the report.

What adjustments would you like to make?"""

    # 获取用户输入
    user_input = interrupt(user_prompt)
    
    # 如果用户选择完成报告
    if isinstance(user_input, bool) and user_input is True:
        return Command(goto=END)
    
    # 解析用户输入
    if isinstance(user_input, str) or isinstance(user_input, dict):
        try:
            import json
            # 尝试解析为JSON
            if isinstance(user_input, str):
                adjustment_data = json.loads(user_input)
            else:
                adjustment_data = user_input
            
            # 如果是单个调整，包装成列表
            if isinstance(adjustment_data, dict):
                adjustment_data = [adjustment_data]
            
            adjustments = [SectionAdjustment(**adj) for adj in adjustment_data]
        except (json.JSONDecodeError, Exception):
            # 如果解析失败，返回错误并重新请求
            return Command(
                goto="adjust_sections",
                update={"adjustment_error": f"Invalid input format. Please provide valid JSON or 'true' to finish."}
            )
    elif isinstance(user_input, list):
        try:
            adjustments = [SectionAdjustment(**adj) if isinstance(adj, dict) else adj for adj in user_input]
        except Exception:
            return Command(
                goto="adjust_sections", 
                update={"adjustment_error": "Invalid adjustment format."}
            )
    else:
        return Command(
            goto="adjust_sections",
            update={"adjustment_error": "Please provide adjustments or 'true' to finish."}
        )
    
    # 处理调整：只修改需要调整的sections
    sections = state["sections"].copy()
    has_research_sections = False  # 是否有需要重新研究的章节
    
    for adjustment in adjustments:
        try:
            if adjustment.action == "add":           
                # 将SectionPlan转换为Section（添加内部管理字段）
                new_section = Section(
                    id=str(uuid.uuid4()),
                    name=adjustment.section_name,
                    description=adjustment.section_name,
                    research=True,
                    content="",
                    sources=[],
                    sections=None,
                    status="pending"
                )
                sections = add_section_at_path(sections, adjustment.section_path, new_section)
                
                # 如果新section需要研究，标记有需要研究的章节
                if new_section.research:
                    has_research_sections = True
                
            elif adjustment.action == "delete":
                sections = delete_section_at_path(sections, adjustment.section_path)
                
            elif adjustment.action == "modify":
                if adjustment.modification_prompt is None:
                    continue
                    
                try:
                    section_to_modify, _, _ = find_section_by_path(sections, adjustment.section_path)
                    
                    # 清空内容，准备重新生成
                    section_to_modify.content = ""
                    section_to_modify.sources = []
                    section_to_modify.status = "pending"  # 重置状态为待处理
                    
                    # 更新描述以包含修改要求
                    section_to_modify.description = f"{section_to_modify.description}. {adjustment.modification_prompt}"
                    
                    # 如果section需要研究，标记有需要研究的章节
                    if section_to_modify.research:
                        has_research_sections = True
                        
                except (ValueError, IndexError):
                    continue
                    
        except Exception as e:
            # 如果单个调整失败，继续处理其他调整
            continue
    

    # 遍历所有sections，将不需要research的section状态改为pending，以便重新生成
    def reset_non_research_sections(sections_list: list[Section]):
        """递归重置所有不需要研究的章节状态为pending"""
        for section in sections_list:
            if not section.research:
                section.status = "pending"
                section.content = ""  # 清空内容，准备重新生成
                section.sources = []  # 清空来源
        
            # 递归处理子章节
            if section.sections:
                reset_non_research_sections(section.sections)
    
    reset_non_research_sections(sections)

    # 更新状态，清空completed_section以避免重复处理
    update_dict = {"sections": sections, "completed_section": "CLEAR"}
    
    return Command(
        update=update_dict,
        goto="process_adjustment_research"
    )

def process_adjustment_research(state: ReportState) -> Command:
    """处理调整后需要研究的sections（通过status字段收集）"""
    
    def collect_pending_research_sections(sections: list[Section]) -> list[Section]:
        """递归收集所有状态为pending且需要研究的章节"""
        pending_sections = []
        for section in sections:
            # 如果当前章节需要研究且状态为pending，添加到列表
            if section.research and section.status == "pending":
                section.status = "in_progress"  # 标记为进行中
                pending_sections.append(section)
            
            # 递归处理子章节
            if section.sections:
                pending_sections.extend(collect_pending_research_sections(section.sections))
        
        return pending_sections
    
    # 收集所有需要研究的章节
    sections_to_research = collect_pending_research_sections(state["sections"])
    
    if not sections_to_research:
        # 如果没有需要研究的sections，直接编译报告
        return Command(goto="gather_completed_sections")
    
    topic = state["topic"]
    local_sources_str = state.get("local_sources_str", "")
    
    # 启动需要研究的sections的并行研究
    return Command(goto=[
        Send("build_section_with_web_research", {
            "topic": topic, 
            "section": section,
            "search_iterations": 0, 
            "local_sources_str": local_sources_str
        }) for section in sections_to_research
    ])

# Report section sub-graph -- 

# Add nodes 
section_builder = StateGraph(SectionState, output=SectionOutputState)
section_builder.add_node("generate_queries", generate_queries)
section_builder.add_node("search_web", search_web)
section_builder.add_node("write_section", write_section)

# Add edges
section_builder.add_edge(START, "generate_queries")
section_builder.add_edge("generate_queries", "search_web")
section_builder.add_edge("search_web", "write_section")

# Outer graph for initial report plan compiling results from each section -- 

# Add nodes
builder = StateGraph(ReportState, input=ReportStateInput, output=ReportStateOutput, config_schema=WorkflowConfiguration)
builder.add_node("generate_report_plan", generate_report_plan)
builder.add_node("human_feedback", human_feedback)
builder.add_node("build_section_with_web_research", section_builder.compile())
builder.add_node("gather_completed_sections", gather_completed_sections)
builder.add_node("write_final_sections", write_final_sections)
builder.add_node("compile_final_report", compile_final_report)
builder.add_node("adjust_sections", adjust_sections)
builder.add_node("process_adjustment_research", process_adjustment_research)

# Add edges
builder.add_edge(START, "generate_report_plan")
builder.add_edge("generate_report_plan", "human_feedback")
builder.add_edge("build_section_with_web_research", "gather_completed_sections")

# 简化的直接连接流程：
# gather_completed_sections 使用条件边决定是否需要写final sections
builder.add_conditional_edges("gather_completed_sections", gather_sections_router, 
                              ["write_final_sections", "compile_final_report"])
builder.add_edge("write_final_sections", "gather_completed_sections")
builder.add_edge("compile_final_report", "adjust_sections")

# 新增：process_adjustment_research处理调整后的研究
# process_adjustment_research通过Send机制连接到build_section_with_web_research，
# 结果会自动流向gather_completed_sections

# adjust_sections 通过Command处理路由：
# 1. 如果用户选择完成 -> END
# 2. 如果有需要研究的sections -> process_adjustment_research  
# 3. 如果只是删除/不需要研究的修改 -> compile_final_report
# 4. 如果输入错误 -> adjust_sections (重新输入)

graph = builder.compile()
