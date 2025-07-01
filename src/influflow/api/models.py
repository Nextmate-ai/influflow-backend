"""
API请求和响应模型
定义Twitter AI功能的HTTP接口数据结构
"""

from typing import Optional, Literal, List
from pydantic import BaseModel, Field


# =========================
# Twitter Thread数据结构
# =========================

class Tweet(BaseModel):
    """Tweet数据结构"""
    tweet_number: int = Field(..., alias="tweet_number", description="Tweet在线程中的编号", ge=1)
    title: str = Field(..., alias="title", description="Tweet标题", min_length=1, max_length=200)
    content: str = Field(..., alias="content", description="Tweet内容", min_length=1, max_length=280)


class OutlineNode(BaseModel):
    """大纲节点数据结构"""
    title: str = Field(..., alias="title", description="节点标题", min_length=1, max_length=200)
    tweets: List[Tweet] = Field(..., alias="tweets", description="该节点包含的tweets")


class Outline(BaseModel):
    """Twitter Thread大纲数据结构"""
    topic: str = Field(..., alias="topic", description="Thread主题", min_length=1, max_length=1000)
    nodes: List[OutlineNode] = Field(..., alias="nodes", description="大纲节点列表")
    total_tweets: int = Field(..., alias="total_tweets", description="总tweet数量", ge=1)
    
    def get_formatted_thread(self) -> str:
        """获取格式化的thread字符串"""
        all_tweets = []
        for node in self.nodes:
            all_tweets.extend(node.tweets)
        
        # 按tweet_number排序
        all_tweets.sort(key=lambda t: t.tweet_number)
        
        # 格式化输出
        thread_parts = []
        for tweet in all_tweets:
            thread_parts.append(f"({tweet.tweet_number}/{self.total_tweets}) {tweet.content}")
        
        return "\n\n".join(thread_parts)


# =========================
# 请求模型
# =========================

class GenerateThreadRequest(BaseModel):
    """生成Twitter thread请求模型"""
    topic: str = Field(..., alias="topic", description="Twitter thread的主题", min_length=1, max_length=1000)


class ModifyTweetRequest(BaseModel):
    """修改单个Tweet请求模型"""
    outline: Outline = Field(..., alias="outline", description="当前的完整大纲结构")
    tweet_number: int = Field(..., alias="tweet_number", description="要修改的Tweet编号", ge=1)
    modification_prompt: str = Field(..., alias="modification_prompt", description="修改指令", min_length=1, max_length=500)


class ModifyOutlineRequest(BaseModel):
    """修改大纲结构请求模型"""
    original_outline: Outline = Field(..., alias="original_outline", description="原始大纲结构")
    new_outline_structure: Outline = Field(..., alias="new_outline_structure", description="新的大纲结构")


# =========================
# 响应模型
# =========================

class GenerateThreadResponse(BaseModel):
    """生成Twitter thread响应模型"""
    status: Literal["success", "error"] = Field(..., alias="status", description="操作状态")
    outline: Optional[Outline] = Field(None, alias="outline", description="生成的Twitter thread大纲")
    error: Optional[str] = Field(None, alias="error", description="错误信息")


class ModifyTweetResponse(BaseModel):
    """修改Tweet响应模型"""
    status: Literal["success", "error"] = Field(..., alias="status", description="操作状态")
    updated_tweet_content: Optional[str] = Field(None, alias="updated_tweet_content", description="更新后的tweet内容")
    error: Optional[str] = Field(None, alias="error", description="错误信息")


class ModifyOutlineResponse(BaseModel):
    """修改大纲结构响应模型"""
    status: Literal["success", "error"] = Field(..., alias="status", description="操作状态")
    updated_outline: Optional[Outline] = Field(None, alias="updated_outline", description="更新后的完整大纲")
    error: Optional[str] = Field(None, alias="error", description="错误信息")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., alias="status", description="服务状态")
    version: str = Field(..., alias="version", description="版本号")
    timestamp: str = Field(..., alias="timestamp", description="检查时间")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    status: Literal["error"] = Field(..., alias="status", description="错误状态")
    error: str = Field(..., alias="error", description="错误信息")
    detail: Optional[str] = Field(None, alias="detail", description="详细错误信息")


# =========================
# 数据转换函数（API层负责）
# =========================

def convert_internal_outline_to_api(internal_outline) -> Outline:
    """将内部Outline结构转换为API Outline结构"""
    api_nodes = []
    
    for internal_node in internal_outline.nodes:
        api_tweets = []
        for leaf_node in internal_node.leaf_nodes:
            api_tweets.append(Tweet(
                tweet_number=leaf_node.tweet_number,
                title=leaf_node.title,
                content=leaf_node.tweet_content
            ))
        
        api_nodes.append(OutlineNode(
            title=internal_node.title,
            tweets=api_tweets
        ))
    
    # 计算总tweet数量
    total_tweets = sum(len(node.tweets) for node in api_nodes)
    
    return Outline(
        topic=internal_outline.topic,
        nodes=api_nodes,
        total_tweets=total_tweets
    )


def convert_api_outline_to_internal(api_outline: Outline):
    """将API Outline结构转换为内部Outline结构"""
    # 导入内部结构（只在需要时导入，避免循环依赖）
    from influflow.ai.state import Outline as InternalOutline, OutlineNode as InternalNode, OutlineLeafNode as InternalLeaf
    
    internal_nodes = []
    
    for api_node in api_outline.nodes:
        leaf_nodes = []
        for api_tweet in api_node.tweets:
            leaf_nodes.append(InternalLeaf(
                title=api_tweet.title,
                tweet_number=api_tweet.tweet_number,
                tweet_content=api_tweet.content
            ))
        
        internal_nodes.append(InternalNode(
            title=api_node.title,
            leaf_nodes=leaf_nodes
        ))
    
    return InternalOutline(
        topic=api_outline.topic,
        nodes=internal_nodes
    )


def update_tweet_in_internal_outline(internal_outline, tweet_number: int, new_content: str):
    """更新内部outline中指定编号的tweet内容"""
    for node in internal_outline.nodes:
        for leaf_node in node.leaf_nodes:
            if leaf_node.tweet_number == tweet_number:
                leaf_node.tweet_content = new_content
                break
    return internal_outline 