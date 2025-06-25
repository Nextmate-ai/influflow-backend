from typing import Annotated, List, TypedDict, Literal, Optional, NotRequired, Union
from pydantic import BaseModel, Field
import operator
import uuid

class Source(BaseModel):
    type: Literal["web", "local"] = Field(
        description="Type of the source."
    )
    id: str = Field(
        description="ID of the source. It is url for web sources and index for local sources."
    )
    title: str = Field(
        description="Title of the source. It is optional and only used for web sources."
    )
    excerpt: str = Field(
        description="Original text excerpt from the source, must be exact and unmodified from the original source. This is a relevant paragraph not the full text."
    )

class SectionPlan(BaseModel):
    """章节计划模型，用于大模型生成，不包含内部管理字段"""
    name: str = Field(
        description="Name for this section of the report. It should be pure text, no markdown or other formatting like 1./*/a.",
    )
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section.",
    )
    research: bool = Field(
        description="Whether to perform web research for this section of the report."
    )
    content: str = Field(
        default="",
        description="The content of the section."
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Sources of the section. This is a list of formatted source content from web search."
    )
    # 递归结构：支持子章节，类似思维导图
    sections: Optional[List["SectionPlan"]] = Field(
        default=None,
        description="List of sub-sections under this section, supporting hierarchical structure like mind map."
    )

class Section(BaseModel):
    """完整的章节模型，用于内部管理，包含状态字段"""
    id: str = Field(
        description="ID for this section of the report. It is a unique identifier for the section."
    )
    name: str = Field(
        description="Name for this section of the report. It should be pure text, no markdown or other formatting like 1./*/a.",
    )
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section.",
    )
    research: bool = Field(
        description="Whether to perform web research for this section of the report."
    )
    content: str = Field(
        description="The content of the section."
    )
    sources: list[Source] = Field(
        description="Sources of the section. This is a list of formatted source content from web search."
    )
    # 递归结构：支持子章节，类似思维导图
    sections: Optional[List["Section"]] = Field(
        default=None,
        description="List of sub-sections under this section, supporting hierarchical structure like mind map."
    )
    # 内部管理字段：章节完成状态
    status: Literal["pending", "completed", "in_progress"] = Field(
        default="pending",
        description="Status of the section: pending (not started), in_progress (being researched), completed (finished)"
    )

class SectionContent(BaseModel):
    content: str = Field(
        description="Content of the section."
    )
    sources: list[Source] = Field(
        description="Sources of the section. This is a list of formatted source content from web search. Example format: Source Title: URL"
    )

class Sections(BaseModel):
    sections: List[Section] = Field(
        description="Sections of the report.",
    )

class SectionsPlan(BaseModel):
    """章节计划列表，用于大模型生成"""
    sections: List[SectionPlan] = Field(
        description="Sections of the report plan.",
    )

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Query for web search.")

class Queries(BaseModel):
    queries: List[SearchQuery] = Field(
        description="List of search queries.",
    )

class Feedback(BaseModel):
    grade: Literal["pass","fail"] = Field(
        description="Evaluation result indicating whether the response meets requirements ('pass') or needs revision ('fail')."
    )
    follow_up_queries: List[SearchQuery] = Field(
        description="List of follow-up search queries.",
    )

class ReportStateInput(TypedDict):
    topic: str # Report topic
    local_sources: NotRequired[list[str]] # 用户提供的本地源文本内容，可选字段

class ReportStateOutput(TypedDict):
    final_report: str # Final report
    # for evaluation purposes only
    # this is included only if configurable.include_source_str is True
    source_str: str # String of formatted source content from web search

# 在class定义之前添加自定义reducer函数
def manage_completed_sections(existing: list[Section], update: Union[list[Section], str]) -> list[Section]:
    """
    自定义reducer函数，用于管理completed_section字段
    支持正常的累加操作和清空操作
    
    Args:
        existing: 当前的completed_section列表
        update: 更新内容，可以是Section列表或"CLEAR"字符串
        
    Returns:
        更新后的Section列表
    """
    if update == "CLEAR":
        return []
    if isinstance(update, list):
        return (existing or []) + update
    return existing or []

class ReportState(TypedDict):
    topic: str # Report topic
    report_plan_context: str # Context of the report plan
    local_sources: list[str] # 用户提供的本地源文本内容列表
    local_sources_str: str # 用户提供的本地源文本内容字符串
    feedback_on_report_plan: str # Latest feedback on the report plan
    sections: list[Section] # List of report sections with embedded status
    report_sections_from_research: str # String of any completed sections from research to write final sections
    final_report: str # Final report
    
    # for handling multiple completed sections from parallel subgraphs
    completed_section: Annotated[list[Section], manage_completed_sections] # Collect completed sections from subgraphs with custom clear support
    
    # for evaluation purposes only
    # this is included only if configurable.include_source_str is True
    source_str: Annotated[str, operator.add] # String of formatted source content from web search

class SectionState(TypedDict):
    topic: str # Report topic
    section: Section # Report section  
    search_iterations: int # Number of search iterations done
    search_queries: list[SearchQuery] # List of search queries
    source_str: str # String of formatted source content from web search
    local_sources_str: str # 用户提供的本地源文本内容字符串
    report_sections_from_research: str # String of any completed sections from research to write final sections

class SectionOutputState(TypedDict):
    # The section will have its status updated to "completed" internally
    completed_section: list[Section] # List containing the updated section object with content, sources, and status
    # for evaluation purposes only
    # this is included only if configurable.include_source_str is True
    source_str: NotRequired[str] # String of formatted source content from web search

# 更新前向引用，使递归结构生效
SectionPlan.model_rebuild()
Section.model_rebuild()

# === 文章体裁和写作风格调整相关State定义 ===

class StylerInput(TypedDict):
    """文章体裁调整的输入状态"""
    original_text: str  # 原始文章内容
    tag: str  # 体裁标签，如"tweet", "blog_post", "academic", "casual"等
    custom_prompt: NotRequired[str]  # 可选的自定义提示词
    reference_text: NotRequired[str]  # 可选的参考文本，用于学习写作风格

class StylerOutput(TypedDict):
    """文章体裁调整的输出状态"""
    styled_text: str  # 调整后的文章

class StylerState(TypedDict):
    """文章体裁调整的内部状态"""
    original_text: str  # 原始文章内容
    tag: str  # 体裁标签
    custom_prompt: str  # 自定义提示词（内部处理时统一为字符串）
    reference_text: str  # 参考文本（内部处理时统一为字符串）
    style_analysis: str  # 风格分析结果
    styled_text: str  # 最终调整后的文章

# === Section调整相关State定义 ===

class SectionAdjustment(BaseModel):
    """Section调整指令"""
    action: Literal["add", "delete", "modify"] = Field(
        description="调整动作：添加、删除或修改section"
    )
    section_path: str = Field(
        description="Section路径，使用点分隔的数字表示，如'1'表示第一个顶级section，'1.2'表示第一个section的第二个subsection"
    )
    section_name: Optional[str] = Field(
        default=None,
        description="Section名称，用于辅助定位和验证"
    )
    modification_prompt: Optional[str] = Field(
        default=None,
        description="修改section时的具体调整要求"
    )

def convert_section_plan_to_section(section_plan: SectionPlan) -> Section:
    """将SectionPlan转换为Section，添加内部管理字段"""
    # 递归转换子章节
    converted_sections = None
    if section_plan.sections:
        converted_sections = [convert_section_plan_to_section(sub) for sub in section_plan.sections]
    
    return Section(
        id=str(uuid.uuid4()),
        name=section_plan.name,
        description=section_plan.description,
        research=section_plan.research,
        content=section_plan.content,
        sources=section_plan.sources,
        sections=converted_sections,
        status="pending"  # 默认状态为pending
    )

def convert_sections_plan_to_sections(sections_plan: SectionsPlan) -> List[Section]:
    """将SectionsPlan转换为Section列表"""
    return [convert_section_plan_to_section(section) for section in sections_plan.sections]


