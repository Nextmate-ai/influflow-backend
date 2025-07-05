"""
测试用户输入分析功能
"""

import pytest
from influflow.ai.graph.generate_tweet import graph


@pytest.mark.asyncio
async def test_user_input_analysis_english():
    """测试英文输入的分析"""
    # 英文输入，应该输出英文推文
    result = await graph.ainvoke({
        "user_input": "Write a thread about how AI is changing software development"
    })
    
    assert result["outline"] is not None
    assert result["outline"].topic is not None
    assert "AI" in result["outline"].topic or "software" in result["outline"].topic
    # 检查输出是否为英文（通过检查第一个tweet是否包含英文字符）
    first_tweet = result["outline"].nodes[0].leaf_nodes[0].tweet_content
    assert any(c.isascii() and c.isalpha() for c in first_tweet)


@pytest.mark.asyncio
async def test_user_input_analysis_chinese():
    """测试中文输入的分析"""
    # 中文输入，应该输出中文推文
    result = await graph.ainvoke({
        "user_input": "写一个关于人工智能如何改变软件开发的推文串"
    })
    
    assert result["outline"] is not None
    assert result["outline"].topic is not None
    # 检查输出是否为中文（通过检查第一个tweet是否包含中文字符）
    first_tweet = result["outline"].nodes[0].leaf_nodes[0].tweet_content
    assert any('\u4e00' <= c <= '\u9fff' for c in first_tweet)


@pytest.mark.asyncio
async def test_user_input_analysis_explicit_language():
    """测试明确指定语言的输入"""
    # 英文输入但要求中文输出
    result = await graph.ainvoke({
        "user_input": "Write a thread about machine learning in Chinese"
    })
    
    assert result["outline"] is not None
    # 检查输出是否为中文
    first_tweet = result["outline"].nodes[0].leaf_nodes[0].tweet_content
    assert any('\u4e00' <= c <= '\u9fff' for c in first_tweet)