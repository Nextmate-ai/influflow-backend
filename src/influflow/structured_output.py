from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class OutlineNodeOutput(BaseModel):
    """LLM output structure for outline nodes - 递归层次结构"""
    title: str = Field(
        description="Node title, concise and clear"
    )
    description: str = Field(
        description="Brief content description to guide Twitter content creation, explaining what this node will cover"
    )
    level: Literal[1, 2, 3] = Field(
        description="Node level: 1 for main branches, 2 for sub-branches, 3 for specific points (corresponding to individual tweets)"
    )
    children: List["OutlineNodeOutput"] = Field(
        default_factory=list,
        description="Child nodes list, forming hierarchical structure"
    )

class OutlineStructure(BaseModel):
    """Twitter thread outline structure - 递归层次结构包装类"""
    nodes: List[OutlineNodeOutput] = Field(
        description="List of top-level outline nodes with hierarchical structure. Each node can have children to form a tree structure."
    )

class AdjustedOutlineNodeOutput(BaseModel):
    """LLM output structure for adjusted outline nodes - 递归层次结构"""
    id: str = Field(
        description="Node ID, unique identifier for the node"
    )
    title: str = Field(
        description="Node title, concise and clear"
    )
    description: str = Field(
        description="Brief content description to guide Twitter content creation, explaining what this node will cover"
    )
    level: Literal[1, 2, 3] = Field(
        description="Node level: 1 for main branches, 2 for sub-branches, 3 for specific points (corresponding to individual tweets)"
    )
    children: List["AdjustedOutlineNodeOutput"] = Field(
        default_factory=list,
        description="Child nodes list, forming hierarchical structure"
    )

class AdjustedOutlineStructure(BaseModel):
    """Twitter thread outline structure with adjusted nodes - 递归层次结构包装类"""
    nodes: List[AdjustedOutlineNodeOutput] = Field(
        description="List of top-level outline nodes with hierarchical structure. Each node can have children to form a tree structure."
    )

class TweetOutput(BaseModel):
    """LLM output structure for individual tweets"""
    content: str = Field(
        description="Tweet content that complies with Twitter character limits and best practices (MUST be under 280 characters). Include hashtags directly in the content (1-2 max, don't overuse)."
    )

class BatchTweetOutput(BaseModel):
    """Batch-generated Twitter thread structure"""
    tweets: List[TweetOutput] = Field(
        description="Generated tweet list arranged in outline order to form a coherent thread"
    )

# 更新前向引用以支持递归结构
OutlineNodeOutput.model_rebuild()
AdjustedOutlineNodeOutput.model_rebuild()
