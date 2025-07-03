from typing import Annotated, List, TypedDict, Literal, Optional, NotRequired, Union
from pydantic import BaseModel, Field
from enum import Enum
import operator
import uuid

class OutlineLeafNode(BaseModel):
    """Leaf node - represents a single Tweet"""
    title: str = Field(
        description="Node title, concise and clear",
    )
    tweet_number: int = Field(
        description="Tweet number in the thread sequence",
    )
    tweet_content: str = Field(
        description="Tweet content including emojis and hashtags, must be under 280 characters. It MUST only include the tweet content, no other text."
    )

class OutlineNode(BaseModel):
    """First-level node - represents a thematic section"""
    title: str = Field(
        description="Section title describing the theme of this part"
    )
    leaf_nodes: List[OutlineLeafNode] = Field(
        description="List of leaf nodes - tweets contained in this section",
    )

class Outline(BaseModel):
    """Mind map outline"""
    topic: str = Field(
        description="Outline topic"
    )
    nodes: List[OutlineNode] = Field(
        description="List of outline nodes"
    )
    
    def display_tweet_thread(self) -> str:
        """Display tweet thread
        
        Returns:
            Formatted tweet thread string in format: (1/n) tweet1, (2/n) tweet2...
        """
        # 收集所有的tweet内容
        all_tweets = []
        for node in self.nodes:
            for leaf_node in node.leaf_nodes:
                all_tweets.append(leaf_node.tweet_content)
        
        # 计算总数
        total_tweets = len(all_tweets)
        
        # 格式化输出
        tweet_thread = []
        for i, tweet in enumerate(all_tweets, 1):
            tweet_thread.append(f"({i}/{total_tweets}) {tweet}")
        
        # 用两个换行符分隔每个tweet
        return "\n\n".join(tweet_thread)
    
    def display_outline(self) -> str:
        """Display outline structure
        
        Returns:
            Formatted outline string with indentation showing hierarchy
        """
        outline_lines = []
        
        # 添加主题作为标题
        outline_lines.append(f"Topic: {self.topic}")
        outline_lines.append("")  # 空行分隔
        
        # 遍历所有节点
        for node in self.nodes:
            # 第一层节点
            outline_lines.append(f"- {node.title}")
            
            # 第二层叶子节点（缩进3个空格）
            for leaf_node in node.leaf_nodes:
                outline_lines.append(f"   - {leaf_node.title}")
        
        return "\n".join(outline_lines)


class UserInputAnalysis(BaseModel):
    """用户输入分析结果"""
    topic: str = Field(description="The topic the user wants to write about")
    language: str = Field(description="The language for the output (e.g., 'English', 'Chinese', 'Spanish')")

class ToneStyle(str, Enum):
    """推文语调风格枚举"""
    CONVERSATIONAL = "Conversational"  # 对话式：使用第二人称、缩写和友好的问题；轻量使用表情符号(≤2)和感叹号；保持句子简短易懂
    HUMOROUS = "Humorous"  # 幽默式：注入巧妙的双关语、网络梗或流行文化引用，偶尔使用大写强调；最多2个表情符号；幽默必须保持品牌安全(PG-13)
    ANALYTICAL = "Analytical"  # 分析式：以关键统计数据开头；呈现事实→解读→要点；简洁引用来源；不使用表情符号，最少感叹号
    MOTIVATIONAL = "Motivational"  # 激励式：使用充满活力的动词("build, create")、积极形容词，总共一个动力表情符号(🚀/🔥/🌟)；融入成功故事和前瞻性行动号召
    EXPERT = "Expert"  # 专家式：使用精确术语、正式语域和标准或白皮书引用；避免俚语、表情符号和感叹号；从TL;DR到详细影响的结构

class Personalization(BaseModel):
    """个性化设置"""
    account_name: Optional[str] = Field(
        None,
        description="Account name, e.g., @elonmusk"
    )
    identity: Optional[str] = Field(
        None,
        description="Identity positioning, e.g., 'AI Founder', 'Web3 Builder', 'Tech Entrepreneur'"
    )
    tone: Optional[ToneStyle] = Field(
        None,
        description="Tweet writing tone"
    )
    bio: Optional[str] = Field(
        None,
        description="User's custom self-introduction including background, expertise, values, etc. Recommended under 200 characters"
    )
    tweet_examples: Optional[List[str]] = Field(
        None,
        description="User's past tweets or tweet threads as writing style reference. Maximum 3 examples allowed.",
        max_length=3
    )

    def format_personalization(self) -> str:
        """Format personalization"""
        personalization_parts = []
        if self.account_name:
            personalization_parts.append(f"Account Name: {self.account_name}")
        if self.identity:
            personalization_parts.append(f"Identity: {self.identity}")
        if self.tone:
            personalization_parts.append(f"Tone: {self.tone}")
        if self.bio:
            personalization_parts.append(f"Bio: {self.bio}")
        if self.tweet_examples:
            personalization_parts.append("Tweet Examples:")
            for i, example in enumerate(self.tweet_examples, 1):
                personalization_parts.append(f"Example {i}: {example}")
        return "\n".join(personalization_parts)


# =========================
# Graph输入输出接口定义
# =========================

class UserInput(TypedDict):
    """用户的原始输入"""
    user_input: str  # 用户输入的原始文本
    personalization: Personalization


class GenerateTweetInput(TypedDict):
    """生成Twitter thread的输入接口"""
    topic: str  # 推文主题
    language: str  # 推文语言


class GenerateTweetOutput(TypedDict):
    """生成Twitter thread的输出接口"""
    outline: Outline  # 生成的outline结构


class ModifySingleTweetInput(TypedDict):
    """修改单个tweet的输入接口"""
    outline: Outline  # 当前的outline结构
    tweet_number: int  # 要修改的tweet编号（从1开始）
    modification_prompt: str  # 修改提示词，描述如何修改


class ModifySingleTweetOutput(TypedDict):
    """修改单个tweet的输出接口"""
    updated_tweet: str  # 修改后的tweet内容


class ModifyOutlineStructureInput(TypedDict):
    """修改outline结构的输入接口"""
    original_outline: Outline  # 原始的outline结构
    new_outline_structure: Outline  # 新的outline结构模板


class ModifyOutlineStructureOutput(TypedDict):
    """修改outline结构的输出接口"""
    outline: Outline  # 更新后的完整outline结构


# =========================
# Graph状态定义（兼容LangGraph）
# =========================

class InfluflowState(TypedDict):
    """生成Twitter thread的状态"""
    # 用户输入字段
    user_input: str  # 用户原始输入（必需的输入）
    personalization: NotRequired[Personalization]  # 个性化设置
    # 中间处理字段（由AI分析得出）
    topic: NotRequired[str]  # 主题（从user_input分析得出）
    language: NotRequired[str]  # 语言（从user_input分析得出）
    # 输出字段
    outline: NotRequired[Outline]  # 生成的outline
    outline_str: NotRequired[str]  # outline字符串表示
    tweet_thread: NotRequired[str]  # 推文串


class ModifySingleTweetState(TypedDict):
    """修改单个tweet的状态"""
    # 输入字段
    outline: Outline  # 要修改的outline
    tweet_number: int  # 要修改的tweet编号（从1开始）
    modification_prompt: str  # 修改提示词
    # 输出字段
    tweet_thread: NotRequired[str]  # 更新后的完整推文串


class ModifyOutlineStructureState(TypedDict):
    """修改outline结构的状态"""
    # 输入字段
    original_outline: Outline  # 原始outline
    new_outline_structure: Outline  # 新的outline结构
    # 输出字段
    outline: NotRequired[Outline]  # 更新后的outline