import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Tweet(BaseModel):
    """
    代表推文串中的单条推文。
    """
    title: str = Field(description="内部用于组织的标题，简洁清晰")
    tweet_number: int = Field(description="推文在整个线程中的顺序号")
    content: str = Field(description="推文内容，包含表情符号和标签，必须在280个字符以内。")
    image_url: Optional[str] = Field(default=None, description="推文图片的URL")


class TweetSection(BaseModel):
    """
    代表推文串的一个主题章节。
    """
    title: str = Field(description="本部分主题的章节标题")
    tweets: List[Tweet] = Field(description="本章节包含的推文列表")


class TweetThread(BaseModel):
    """
    代表一个完整的推文串，用于持久化存储。
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="唯一标识符")
    uid: str = Field(description="创建此推文串的用户的ID")
    topic: str = Field(description="推文串的主题")
    tweets: List[TweetSection] = Field(description="推文串的章节列表，将作为JSONB存储")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最后更新时间")