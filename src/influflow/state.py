from typing import Annotated, List, TypedDict, Literal, Optional, NotRequired, Union
from pydantic import BaseModel, Field
import operator
import uuid

class OutlineNode(BaseModel):
    """思维导图大纲节点，支持最多三层结构"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="节点的唯一标识符，使用UUID生成"
    )
    title: str = Field(
        description="节点标题，简洁明了"
    )
    description: str = Field(
        description="节点详细描述，解释这个节点要表达的核心内容"
    )
    level: Literal[1, 2, 3] = Field(
        description="节点层级：1为主要分支，2为次要分支，3为具体要点（对应具体tweet）"
    )
    children: List["OutlineNode"] = Field(
        default_factory=list,
        description="子节点列表"
    )
    # 状态管理
    status: Literal["pending", "completed", "in_progress"] = Field(
        default="pending",
        description="节点状态：pending（待处理）、in_progress（进行中）、completed（已完成）"
    )

class Tweet(BaseModel):
    """单个tweet内容"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Tweet的唯一标识符，使用UUID生成"
    )
    content: str = Field(
        description="Tweet内容，包含hashtag，需要符合Twitter字符限制和最佳实践"
    )
    outline_node_id: str = Field(
        description="对应的大纲节点ID（通常是第三层节点）"
    )
    thread_position: int = Field(
        description="在thread中的位置序号，从1开始"
    )

class TweetThread(BaseModel):
    """Tweet thread整体"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Thread的唯一标识符，使用UUID生成"
    )
    topic: str = Field(
        description="Thread主题"
    )
    tweets: List[Tweet] = Field(
        description="组成thread的tweet列表，按顺序排列"
    )
    total_tweets: int = Field(
        description="Thread中tweet的总数"
    )

class OutlineAdjustment(BaseModel):
    """大纲调整指令 - 使用位置编号进行操作"""
    action: Literal["add", "delete", "modify"] = Field(
        description="调整动作：添加、删除、修改节点"
    )
    position: str = Field(
        description="节点位置编号，如 '1'、'2.1'、'3.2.1' 等，对应大纲显示的编号"
    )
    new_title: Optional[str] = Field(
        default=None,
        description="新的节点标题（用于添加或修改）"
    )

class SearchQuery(BaseModel):
    """搜索查询"""
    search_query: str = Field(
        description="搜索查询内容"
    )

class Queries(BaseModel):
    """搜索查询列表"""
    queries: List[SearchQuery] = Field(
        description="搜索查询列表"
    )

# 输入输出状态定义
class InfluflowStateInput(TypedDict):
    """Influflow工作流输入状态"""
    topic: str  # 用户提供的主题

class InfluflowStateOutput(TypedDict):
    """Influflow工作流输出状态"""
    final_tweet_thread: str  # 最终的tweet thread内容
    outline_structure: str   # 大纲结构（用于展示）


class InfluflowState(TypedDict):
    """Influflow工作流主状态"""
    topic: str  # 主题
    
    # 大纲相关
    outline_nodes: List[OutlineNode]  # 思维导图大纲节点列表
    outline_context: str  # 大纲生成的搜索上下文
    feedback_on_outline: str  # 用户对大纲的反馈
    
    # Tweet thread相关
    tweet_thread: Optional[TweetThread]  # 生成的tweet thread
    feedback_on_thread: str  # 用户对thread的反馈
    
    # 搜索相关
    search_context: Annotated[str, operator.add]  # 搜索上下文累积
    
    # 工作流状态
    current_phase: Literal["outline_generation", "outline_adjustment", "thread_generation", "thread_adjustment", "completed"]

class OutlineGenerationState(TypedDict):
    """大纲生成子图状态"""
    topic: str
    search_queries: List[SearchQuery]
    search_context: str
    outline_nodes: List[OutlineNode]

class TweetGenerationState(TypedDict):
    """Tweet生成子图状态"""
    topic: str
    outline_node: OutlineNode  # 要生成tweet的大纲节点
    search_queries: List[SearchQuery]
    search_context: str
    generated_tweet: Tweet

# 更新前向引用
OutlineNode.model_rebuild()
