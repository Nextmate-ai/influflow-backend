# -*- coding: utf-8 -*-
"""
pytest configuration and shared fixtures for influflow tests

配置 pytest 和共享的测试fixtures
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from typing import Dict, Any

# 导入项目模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_state():
    """提供示例状态数据"""
    return {
        "topic": "AI 对创作者的影响",
        "language": "Chinese"
    }


@pytest.fixture
def mock_llm_config():
    """模拟 LLM 配置"""
    return MagicMock()


@pytest.fixture
def sample_valid_tweets():
    """提供示例有效推文"""
    return [
        {
            "content": "这是一条测试推文，包含足够的字符来满足250字符的最低要求。我们会添加更多内容来确保达到要求的长度限制。这条推文应该包含有价值的信息，同时保持在规定的字符范围内。使用适当的hashtag和emoji来增加参与度。 #TestHashtag 🚀",
            "char_count": 138,
            "has_bullets": False,
            "hashtag_count": 1,
            "emoji_count": 1
        },
        {
            "content": "这是第二条推文，提供有价值的内容：\n• 第一个重要观点\n• 第二个关键信息\n• 第三个有价值见解\n这样的格式有助于提高可读性和参与度。我们确保内容既有用又符合字符要求。 #Content #Tips 🚀✨",
            "char_count": 120,
            "has_bullets": True,
            "hashtag_count": 2,
            "emoji_count": 2
        }
    ]


@pytest.fixture
def sample_invalid_tweets():
    """提供示例无效推文"""
    return [
        {
            "content": "Too short! 🚀",
            "issues": ["字符数不足"]
        },
        {
            "content": "这是一条包含错误 bullet 格式的推文： • 第一个要点 • 第二个要点 • 第三个要点 这样的格式是错误的。",
            "issues": ["bullet points 没有正确换行"]
        },
        {
            "content": "这是一条包含过多hashtag的推文。 #Tag1 #Tag2 #Tag3 #Tag4 #Tag5 🚀",
            "issues": ["hashtag 数量超过限制"]
        }
    ] 