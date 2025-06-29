from typing import Annotated, List, TypedDict, Literal, Optional, NotRequired, Union
from pydantic import BaseModel, Field
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


class InfluflowState(TypedDict):
    """Influflow workflow main state"""
    topic: str  # Topic
    language: str  # Language
    outline: Outline  # Outline
    outline_str: str  # Outline string representation
    tweet_thread: str  # Tweet thread string