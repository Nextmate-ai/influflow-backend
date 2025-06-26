import os
import asyncio
import json
import datetime
import requests
import random 
import concurrent
import hashlib
import aiohttp
import httpx
import time
from typing import List, Optional, Dict, Any, Union, Literal, Annotated, cast, Tuple
from urllib.parse import unquote
from collections import defaultdict
import itertools
import re
import copy

from exa_py import Exa
from linkup import LinkupClient
from tavily import AsyncTavilyClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient as AsyncAzureAISearchClient
from duckduckgo_search import DDGS 
from bs4 import BeautifulSoup
from markdownify import markdownify
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.retrievers import ArxivRetriever
from langchain_community.utilities.pubmed import PubMedAPIWrapper
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from influflow.configuration import WorkflowConfiguration
from influflow.state import OutlineNode, Tweet, TweetThread

def format_outline_display(outline_nodes: List[OutlineNode]) -> str:
    """
    格式化大纲节点为可读的层次结构显示
    
    Args:
        outline_nodes: 大纲节点列表
        
    Returns:
        格式化后的大纲显示字符串
    """
    if not outline_nodes:
        return "No outline nodes available."
    
    def format_node(node: OutlineNode, level: int = 0, is_last: bool = False, prefix: str = "") -> str:
        """递归格式化单个节点"""
        # 根据层级选择不同的图标
        level_icons = {1: "📌", 2: "▸", 3: "•"}
        icon = level_icons.get(node.level, "•")
        
        # 构建当前节点的显示
        indent = "  " * level
        connector = "└─ " if is_last else "├─ "
        
        node_display = f"{prefix}{connector}{icon} [{node.level}] {node.title}\n"
        node_display += f"{prefix}{'   ' if is_last else '│  '}   Description: {node.description}\n"
        node_display += f"{prefix}{'   ' if is_last else '│  '}   Status: {node.status}\n"
        node_display += f"{prefix}{'   ' if is_last else '│  '}   ID: {node.id}\n"
        
        # 递归处理子节点
        if node.children:
            child_prefix = prefix + ("   " if is_last else "│  ")
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                node_display += format_node(child, level + 1, is_last_child, child_prefix)
        
        return node_display
    
    # 格式化所有顶级节点
    result = f"Twitter Thread Outline Structure:\n"
    result += f"{'=' * 50}\n"
    
    for i, node in enumerate(outline_nodes):
        if node.level == 1:  # 只显示顶级节点，子节点会递归显示
            is_last = i == len([n for n in outline_nodes if n.level == 1]) - 1
            result += format_node(node, 0, is_last)
    
    return result

def format_outline_display_titles_only(outline_nodes: List[OutlineNode]) -> str:
    """
    格式化大纲节点为包含ID和标题的XML格式（用于用户调整后的显示）
    
    Args:
        outline_nodes: 大纲节点列表
        
    Returns:
        XML格式的大纲显示字符串，包含每个节点的ID和标题
    """
    if not outline_nodes:
        return "No outline nodes available."
    
    result = "📝 User's Outline Structure (XML Format with IDs and Titles):\n"
    result += "=" * 50 + "\n\n"
    
    # 获取所有顶级节点
    top_level_nodes = [node for node in outline_nodes if node.level == 1]
    
    if not top_level_nodes:
        return result + "(No outline structure available)"
    
    result += "<outline>\n"
    
    for i, node in enumerate(top_level_nodes, 1):
        # Level 1 节点
        result += f'  <node level="1" id="{node.id}" title="{node.title}">\n'
        
        # Level 2 节点
        if node.children:
            for j, child in enumerate(node.children, 1):
                result += f'    <node level="2" id="{child.id}" title="{child.title}">\n'
                
                # Level 3 节点
                if child.children:
                    for k, grandchild in enumerate(child.children, 1):
                        result += f'      <node level="3" id="{grandchild.id}" title="{grandchild.title}" />\n'
                
                result += "    </node>\n"
        
        result += "  </node>\n"
        
        # 在主要部分之间添加空行
        if i < len(top_level_nodes):
            result += "\n"
    
    result += "</outline>\n"
    result += "\nNOTE: Please use the exact same 'id' and 'title' values in your output for proper node matching.\n"
    
    return result

def generate_outline_mindmap(outline_nodes: List[OutlineNode], topic: str) -> str:
    """
    生成简洁的数字编号大纲格式
    
    Args:
        outline_nodes: 大纲节点列表
        topic: 主题
        
    Returns:
        简洁的大纲字符串
    """
    if not outline_nodes:
        return f"Topic: {topic}\n(No outline nodes available)"
    
    outline = f"📝 Twitter Thread Outline: {topic}\n"
    outline += "=" * (len(topic) + 30) + "\n\n"
    
    # 获取所有顶级节点
    top_level_nodes = [node for node in outline_nodes if node.level == 1]
    
    if not top_level_nodes:
        return outline + "(No outline structure available)"
    
    for i, node in enumerate(top_level_nodes, 1):
        # Level 1 节点
        outline += f"{i}. {node.title}\n"
        
        # Level 2 节点
        if node.children:
            for j, child in enumerate(node.children, 1):
                outline += f"   {i}.{j} {child.title}\n"
                
                # Level 3 节点 - tweet内容点
                if child.children:
                    for k, grandchild in enumerate(child.children, 1):
                        outline += f"      {i}.{j}.{k} {grandchild.title}\n"
        
        # 在主要部分之间添加空行
        if i < len(top_level_nodes):
            outline += "\n"
    
    # 添加统计信息
    total_tweets = len(get_all_nodes(outline_nodes))
    
    outline += f"\n📊 Summary: {len(top_level_nodes)} sections, {total_tweets} tweets"
    
    return outline

def build_outline_hierarchy(flat_nodes: List[OutlineNode]) -> List[OutlineNode]:
    """
    将扁平的节点列表构建为层次结构
    根据节点的level字段和在列表中的顺序来推断层级关系
    
    Args:
        flat_nodes: 扁平的节点列表，按照逻辑顺序排列
        
    Returns:
        构建好层次结构的节点列表
    """
    if not flat_nodes:
        return []
    
    # 清空所有节点的children列表
    for node in flat_nodes:
        node.children = []
    
    # 使用栈来跟踪当前各层级的父节点
    # level_stack[i] 保存当前第i+1层的最后一个节点
    level_stack: List[Optional[OutlineNode]] = [None, None, None]  # 支持3层
    root_nodes = []
    
    for node in flat_nodes:
        current_level = node.level
        
        if current_level == 1:
            # 第一层节点，添加到root
            root_nodes.append(node)
            level_stack[0] = node
            level_stack[1] = None  # 清空下层父节点
            level_stack[2] = None
        
        elif current_level == 2:
            # 第二层节点，添加到最近的第一层节点
            if level_stack[0] is not None:
                level_stack[0].children.append(node)
                level_stack[1] = node
                level_stack[2] = None  # 清空下层父节点
        
        elif current_level == 3:
            # 第三层节点，添加到最近的第二层节点
            if level_stack[1] is not None:
                level_stack[1].children.append(node)
                level_stack[2] = node
    
    return root_nodes

def convert_outline_output_to_nodes(outline_outputs: List) -> List[OutlineNode]:
    """
    将LLM输出的递归OutlineNodeOutput结构转换为OutlineNode对象
    
    Args:
        outline_outputs: LLM输出的OutlineNodeOutput列表（递归结构）
        
    Returns:
        转换后的OutlineNode列表（保持递归结构）
    """
    def convert_single_node(output_node) -> OutlineNode:
        # 递归转换子节点
        children = [convert_single_node(child) for child in output_node.children]
        
        # 创建OutlineNode对象
        node = OutlineNode(
            title=output_node.title,
            description=output_node.description,
            level=output_node.level,
            children=children,
            status="pending"
        )
        return node
    
    return [convert_single_node(output) for output in outline_outputs]

def convert_adjusted_outline_output_to_updates(adjusted_outputs: List) -> List[Dict[str, str]]:
    """
    将LLM输出的递归AdjustedOutlineNodeOutput结构转换为节点更新信息
    
    Args:
        adjusted_outputs: LLM输出的AdjustedOutlineNodeOutput列表（递归结构）
        
    Returns:
        包含id和description的更新信息列表，用于批量更新节点
    """
    update_info_list = []
    
    def collect_updates(output_node):
        # 添加当前节点的更新信息
        update_info_list.append({
            "id": output_node.id,
            "description": output_node.description
        })
        
        # 递归处理子节点
        for child in output_node.children:
            collect_updates(child)
    
    for output in adjusted_outputs:
        collect_updates(output)
    
    return update_info_list

def validate_tweet_content(content: str) -> Dict[str, Any]:
    """
    验证tweet内容是否符合Twitter规范
    
    Args:
        content: tweet内容
        
    Returns:
        包含验证结果的字典
    """
    result = {
        "is_valid": True,
        "issues": [],
        "stats": {
            "character_count": len(content),
            "word_count": len(content.split()),
            "hashtag_count": len(re.findall(r'#\w+', content)),
            "mention_count": len(re.findall(r'@\w+', content)),
            "url_count": len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content))
        }
    }
    
    # 检查字符数限制
    if len(content) > 280:
        result["is_valid"] = False
        result["issues"].append(f"Tweet exceeds 280 characters ({len(content)} characters)")
    
    # 检查是否为空
    if not content.strip():
        result["is_valid"] = False
        result["issues"].append("Tweet content is empty")
    
    # 检查hashtag过多
    if result["stats"]["hashtag_count"] > 5:
        result["issues"].append(f"Too many hashtags ({result['stats']['hashtag_count']}). Recommended: 1-2 hashtags")
    
    return result

def format_tweet_thread(tweets: List[Tweet], topic: str) -> str:
    """
    格式化tweet thread为最终显示格式
    
    Args:
        tweets: tweet列表
        topic: 主题
        
    Returns:
        格式化后的thread字符串
    """
    if not tweets:
        return f"Empty thread for topic: {topic}"
    
    # 按position排序
    sorted_tweets = sorted(tweets, key=lambda x: x.thread_position)
    total = len(sorted_tweets)
    
    thread_lines = [
        f"🧵 Twitter Thread: {topic}",
        f"Total tweets: {total}",
        "=" * 50,
        ""
    ]
    
    for tweet in sorted_tweets:
        # 添加tweet编号和内容
        thread_lines.append(f"{tweet.thread_position}/{total}")
        thread_lines.append(tweet.content)
        
        # 添加分隔线（除了最后一条tweet）
        if tweet.thread_position < total:
            thread_lines.append("─" * 30)
        
        thread_lines.append("")
    
    return "\n".join(thread_lines)

def calculate_thread_stats(tweets: List[Tweet]) -> Dict[str, Any]:
    """
    计算thread的统计信息
    
    Args:
        tweets: tweet列表
        
    Returns:
        包含统计信息的字典
    """
    if not tweets:
        return {
            "total_tweets": 0,
            "total_characters": 0,
            "avg_characters": 0,
            "estimated_reading_time": "0 seconds",
            "character_usage": "0%"
        }
    
    total_chars = sum(len(tweet.content) for tweet in tweets)
    avg_chars = total_chars / len(tweets)
    
    # 估算阅读时间（假设平均阅读速度为每分钟200字）
    words = sum(len(tweet.content.split()) for tweet in tweets)
    reading_time_minutes = words / 200
    if reading_time_minutes < 1:
        reading_time = f"{int(reading_time_minutes * 60)} seconds"
    else:
        reading_time = f"{reading_time_minutes:.1f} minutes"
    
    # 计算字符使用率
    max_possible_chars = len(tweets) * 280
    usage_percentage = (total_chars / max_possible_chars) * 100
    
    return {
        "total_tweets": len(tweets),
        "total_characters": total_chars,
        "avg_characters": round(avg_chars, 1),
        "estimated_reading_time": reading_time,
        "character_usage": f"{usage_percentage:.1f}%"
    }

def find_node_by_id(nodes: List[OutlineNode], node_id: str) -> Optional[OutlineNode]:
    """
    根据ID查找节点（递归搜索）
    
    Args:
        nodes: 节点列表
        node_id: 要查找的节点ID
        
    Returns:
        找到的节点，如果没找到返回None
    """
    for node in nodes:
        if node.id == node_id:
            return node
        
        # 递归搜索子节点
        if node.children:
            found = find_node_by_id(node.children, node_id)
            if found:
                return found
    
    return None

def get_level3_nodes(nodes: List[OutlineNode]) -> List[OutlineNode]:
    """
    获取所有第三层节点（用于生成tweets）
    
    Args:
        nodes: 节点列表
        
    Returns:
        所有第三层节点的列表
    """
    level3_nodes = []
    
    def collect_level3(node_list: List[OutlineNode]):
        for node in node_list:
            if node.level == 3:
                level3_nodes.append(node)
            elif node.children:
                collect_level3(node.children)
    
    collect_level3(nodes)
    return level3_nodes

def get_all_nodes(nodes: List[OutlineNode]) -> List[OutlineNode]:
    """
    获取所有节点（用于生成tweets）- 按照层次顺序遍历
    
    Args:
        nodes: 节点列表
        
    Returns:
        所有节点的列表，按照从上到下、从左到右的顺序
    """
    all_nodes = []
    
    def collect_all_nodes(node_list: List[OutlineNode]):
        for node in node_list:
            all_nodes.append(node)
            if node.children:
                collect_all_nodes(node.children)
    
    collect_all_nodes(nodes)
    return all_nodes

def update_node_status(nodes: List[OutlineNode], node_id: str, new_status: str) -> bool:
    """
    更新指定节点的状态
    
    Args:
        nodes: 节点列表
        node_id: 要更新的节点ID
        new_status: 新状态
        
    Returns:
        是否成功更新
    """
    node = find_node_by_id(nodes, node_id)
    if node:
        node.status = new_status
        return True
    return False

def update_nodes_description_by_id(nodes: List[OutlineNode], updated_nodes: List[Dict[str, str]]) -> int:
    """
    根据ID列表批量更新节点的描述信息
    
    Args:
        nodes: 要更新的节点列表
        updated_nodes: 包含id和description的字典列表，格式为 [{"id": "xxx", "description": "yyy"}, ...]
        
    Returns:
        成功更新的节点数量
    """
    updated_count = 0
    
    for update_info in updated_nodes:
        node_id = update_info.get("id")
        new_description = update_info.get("description")
        
        if not node_id or not new_description:
            continue
            
        # 查找并更新节点
        node = find_node_by_id(nodes, node_id)
        if node:
            node.description = new_description
            updated_count += 1
    
    return updated_count

def get_config_value(value):
    """
    Helper function to handle string, dict, and enum cases of configuration values
    """
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value

def get_search_params(search_api: str, search_api_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Filters the search_api_config dictionary to include only parameters accepted by the specified search API.

    Args:
        search_api (str): The search API identifier (e.g., "exa", "tavily").
        search_api_config (Optional[Dict[str, Any]]): The configuration dictionary for the search API.

    Returns:
        Dict[str, Any]: A dictionary of parameters to pass to the search function.
    """
    # Define accepted parameters for each search API
    SEARCH_API_PARAMS = {
        "exa": ["max_characters", "num_results", "include_domains", "exclude_domains", "subpages"],
        "tavily": ["max_results", "topic"],
        "perplexity": [],  # Perplexity accepts no additional parameters
        "arxiv": ["load_max_docs", "get_full_documents", "load_all_available_meta"],
        "pubmed": ["top_k_results", "email", "api_key", "doc_content_chars_max"],
        "linkup": ["depth"],
        "googlesearch": ["max_results"],
    }

    # Get the list of accepted parameters for the given search API
    accepted_params = SEARCH_API_PARAMS.get(search_api, [])

    # If no config provided, return an empty dict
    if not search_api_config:
        return {}

    # Filter the config to only include accepted parameters
    return {k: v for k, v in search_api_config.items() if k in accepted_params}

def deduplicate_and_format_sources(
    search_response,
    max_tokens_per_source=5000,
    include_raw_content=True,
    deduplication_strategy: Literal["keep_first", "keep_last"] = "keep_first"
):
    """
    Takes a list of search responses and formats them into a readable string.
    Limits the raw_content to approximately max_tokens_per_source tokens.
 
    Args:
        search_responses: List of search response dicts, each containing:
            - query: str
            - results: List of dicts with fields:
                - title: str
                - url: str
                - content: str
                - score: float
                - raw_content: str|None
        max_tokens_per_source: int
        include_raw_content: bool
        deduplication_strategy: Whether to keep the first or last search result for each unique URL
    Returns:
        str: Formatted string with deduplicated sources
    """
     # Collect all results
    sources_list = []
    for response in search_response:
        sources_list.extend(response['results'])

    # Deduplicate by URL
    if deduplication_strategy == "keep_first":
        unique_sources = {}
        for source in sources_list:
            if source['url'] not in unique_sources:
                unique_sources[source['url']] = source
    elif deduplication_strategy == "keep_last":
        unique_sources = {source['url']: source for source in sources_list}
    else:
        raise ValueError(f"Invalid deduplication strategy: {deduplication_strategy}")

    # Format output
    formatted_text = "Content from sources:\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"{'='*80}\n"  # Clear section separator
        formatted_text += f"Source: {source['title']}\n"
        formatted_text += f"{'-'*80}\n"  # Subsection separator
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += f"Most relevant content from source: {source['content']}\n===\n"
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = ''
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
        formatted_text += f"{'='*80}\n\n" # End section separator
                
    return formatted_text.strip()

@traceable
async def tavily_search_async(search_queries, max_results: int = 5, topic: Literal["general", "news", "finance"] = "general", include_raw_content: bool = True):
    """
    Performs concurrent web searches with the Tavily API

    Args:
        search_queries (List[str]): List of search queries to process
        max_results (int): Maximum number of results to return
        topic (Literal["general", "news", "finance"]): Topic to filter results by
        include_raw_content (bool): Whether to include raw content in the results

    Returns:
            List[dict]: List of search responses from Tavily API:
                {
                    'query': str,
                    'follow_up_questions': None,      
                    'answer': None,
                    'images': list,
                    'results': [                     # List of search results
                        {
                            'title': str,            # Title of the webpage
                            'url': str,              # URL of the result
                            'content': str,          # Summary/snippet of content
                            'score': float,          # Relevance score
                            'raw_content': str|None  # Full page content if available
                        },
                        ...
                    ]
                }
    """
    tavily_async_client = AsyncTavilyClient()
    search_tasks = []
    for query in search_queries:
            search_tasks.append(
                tavily_async_client.search(
                    query,
                    max_results=max_results,
                    include_raw_content=include_raw_content,
                    topic=topic
                )
            )

    # Execute all searches concurrently
    search_docs = await asyncio.gather(*search_tasks)
    return search_docs

@traceable
async def azureaisearch_search_async(search_queries: list[str], max_results: int = 5, topic: str = "general", include_raw_content: bool = True) -> list[dict]:
    """
    Performs concurrent web searches using the Azure AI Search API.

    Args:
        search_queries (List[str]): list of search queries to process
        max_results (int): maximum number of results to return for each query
        topic (str): semantic topic filter for the search.
        include_raw_content (bool)

    Returns:
        List[dict]: list of search responses from Azure AI Search API, one per query.
    """
    # configure and create the Azure Search client
    # ensure all environment variables are set
    if not all(var in os.environ for var in ["AZURE_AI_SEARCH_ENDPOINT", "AZURE_AI_SEARCH_INDEX_NAME", "AZURE_AI_SEARCH_API_KEY"]):
        raise ValueError("Missing required environment variables for Azure Search API which are: AZURE_AI_SEARCH_ENDPOINT, AZURE_AI_SEARCH_INDEX_NAME, AZURE_AI_SEARCH_API_KEY")
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    credential = AzureKeyCredential(os.getenv("AZURE_AI_SEARCH_API_KEY"))

    reranker_key = '@search.reranker_score'

    async with AsyncAzureAISearchClient(endpoint, index_name, credential) as client:
        async def do_search(query: str) -> dict:
            # search query 
            paged = await client.search(
                search_text=query,
                vector_queries=[{
                    "fields": "vector",
                    "kind": "text",
                    "text": query,
                    "exhaustive": True
                }],
                semantic_configuration_name="fraunhofer-rag-semantic-config",
                query_type="semantic",
                select=["url", "title", "chunk", "creationTime", "lastModifiedTime"],
                top=max_results,
            )
            # async iterator to get all results
            items = [doc async for doc in paged]
            # Umwandlung in einfaches Dict-Format
            results = [
                {
                    "title": doc.get("title"),
                    "url": doc.get("url"),
                    "content": doc.get("chunk"),
                    "score": doc.get(reranker_key),
                    "raw_content": doc.get("chunk") if include_raw_content else None
                }
                for doc in items
            ]
            return {"query": query, "results": results}

        # parallelize the search queries
        tasks = [do_search(q) for q in search_queries]
        return await asyncio.gather(*tasks)


@traceable
def perplexity_search(search_queries):
    """Search the web using the Perplexity API.
    
    Args:
        search_queries (List[SearchQuery]): List of search queries to process
  
    Returns:
        List[dict]: List of search responses from Perplexity API, one per query. Each response has format:
            {
                'query': str,                    # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': list,
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the search result
                        'url': str,              # URL of the result
                        'content': str,          # Summary/snippet of content
                        'score': float,          # Relevance score
                        'raw_content': str|None  # Full content or None for secondary citations
                    },
                    ...
                ]
            }
    """

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}"
    }
    
    search_docs = []
    for query in search_queries:

        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Search the web and provide factual information with sources."
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Parse the response
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", ["https://perplexity.ai"])
        
        # Create results list for this query
        results = []
        
        # First citation gets the full content
        results.append({
            "title": f"Perplexity Search, Source 1",
            "url": citations[0],
            "content": content,
            "raw_content": content,
            "score": 1.0  # Adding score to match Tavily format
        })
        
        # Add additional citations without duplicating content
        for i, citation in enumerate(citations[1:], start=2):
            results.append({
                "title": f"Perplexity Search, Source {i}",
                "url": citation,
                "content": "See primary source for full content",
                "raw_content": None,
                "score": 0.5  # Lower score for secondary sources
            })
        
        # Format response to match Tavily structure
        search_docs.append({
            "query": query,
            "follow_up_questions": None,
            "answer": None,
            "images": [],
            "results": results
        })
    
    return search_docs

@traceable
async def exa_search(search_queries, max_characters: Optional[int] = None, num_results=5, 
                     include_domains: Optional[List[str]] = None, 
                     exclude_domains: Optional[List[str]] = None,
                     subpages: Optional[int] = None):
    """Search the web using the Exa API.
    
    Args:
        search_queries (List[SearchQuery]): List of search queries to process
        max_characters (int, optional): Maximum number of characters to retrieve for each result's raw content.
                                       If None, the text parameter will be set to True instead of an object.
        num_results (int): Number of search results per query. Defaults to 5.
        include_domains (List[str], optional): List of domains to include in search results. 
            When specified, only results from these domains will be returned.
        exclude_domains (List[str], optional): List of domains to exclude from search results.
            Cannot be used together with include_domains.
        subpages (int, optional): Number of subpages to retrieve per result. If None, subpages are not retrieved.
        
    Returns:
        List[dict]: List of search responses from Exa API, one per query. Each response has format:
            {
                'query': str,                    # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': list,
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the search result
                        'url': str,              # URL of the result
                        'content': str,          # Summary/snippet of content
                        'score': float,          # Relevance score
                        'raw_content': str|None  # Full content or None for secondary citations
                    },
                    ...
                ]
            }
    """
    # Check that include_domains and exclude_domains are not both specified
    if include_domains and exclude_domains:
        raise ValueError("Cannot specify both include_domains and exclude_domains")
    
    # Initialize Exa client (API key should be configured in your .env file)
    exa = Exa(api_key = f"{os.getenv('EXA_API_KEY')}")
    
    # Define the function to process a single query
    async def process_query(query):
        # Use run_in_executor to make the synchronous exa call in a non-blocking way
        loop = asyncio.get_event_loop()
        
        # Define the function for the executor with all parameters
        def exa_search_fn():
            # Build parameters dictionary
            kwargs = {
                # Set text to True if max_characters is None, otherwise use an object with max_characters
                "text": True if max_characters is None else {"max_characters": max_characters},
                "summary": True,  # This is an amazing feature by EXA. It provides an AI generated summary of the content based on the query
                "num_results": num_results
            }
            
            # Add optional parameters only if they are provided
            if subpages is not None:
                kwargs["subpages"] = subpages
                
            if include_domains:
                kwargs["include_domains"] = include_domains
            elif exclude_domains:
                kwargs["exclude_domains"] = exclude_domains
                
            return exa.search_and_contents(query, **kwargs)
        
        response = await loop.run_in_executor(None, exa_search_fn)
        
        # Format the response to match the expected output structure
        formatted_results = []
        seen_urls = set()  # Track URLs to avoid duplicates
        
        # Helper function to safely get value regardless of if item is dict or object
        def get_value(item, key, default=None):
            if isinstance(item, dict):
                return item.get(key, default)
            else:
                return getattr(item, key, default) if hasattr(item, key) else default
        
        # Access the results from the SearchResponse object
        results_list = get_value(response, 'results', [])
        
        # First process all main results
        for result in results_list:
            # Get the score with a default of 0.0 if it's None or not present
            score = get_value(result, 'score', 0.0)
            
            # Combine summary and text for content if both are available
            text_content = get_value(result, 'text', '')
            summary_content = get_value(result, 'summary', '')
            
            content = text_content
            if summary_content:
                if content:
                    content = f"{summary_content}\n\n{content}"
                else:
                    content = summary_content
            
            title = get_value(result, 'title', '')
            url = get_value(result, 'url', '')
            
            # Skip if we've seen this URL before (removes duplicate entries)
            if url in seen_urls:
                continue
                
            seen_urls.add(url)
            
            # Main result entry
            result_entry = {
                "title": title,
                "url": url,
                "content": content,
                "score": score,
                "raw_content": text_content
            }
            
            # Add the main result to the formatted results
            formatted_results.append(result_entry)
        
        # Now process subpages only if the subpages parameter was provided
        if subpages is not None:
            for result in results_list:
                subpages_list = get_value(result, 'subpages', [])
                for subpage in subpages_list:
                    # Get subpage score
                    subpage_score = get_value(subpage, 'score', 0.0)
                    
                    # Combine summary and text for subpage content
                    subpage_text = get_value(subpage, 'text', '')
                    subpage_summary = get_value(subpage, 'summary', '')
                    
                    subpage_content = subpage_text
                    if subpage_summary:
                        if subpage_content:
                            subpage_content = f"{subpage_summary}\n\n{subpage_content}"
                        else:
                            subpage_content = subpage_summary
                    
                    subpage_url = get_value(subpage, 'url', '')
                    
                    # Skip if we've seen this URL before
                    if subpage_url in seen_urls:
                        continue
                        
                    seen_urls.add(subpage_url)
                    
                    formatted_results.append({
                        "title": get_value(subpage, 'title', ''),
                        "url": subpage_url,
                        "content": subpage_content,
                        "score": subpage_score,
                        "raw_content": subpage_text
                    })
        
        # Collect images if available (only from main results to avoid duplication)
        images = []
        for result in results_list:
            image = get_value(result, 'image')
            if image and image not in images:  # Avoid duplicate images
                images.append(image)
                
        return {
            "query": query,
            "follow_up_questions": None,
            "answer": None,
            "images": images,
            "results": formatted_results
        }
    
    # Process all queries sequentially with delay to respect rate limit
    search_docs = []
    for i, query in enumerate(search_queries):
        try:
            # Add delay between requests (0.25s = 4 requests per second, well within the 5/s limit)
            if i > 0:  # Don't delay the first request
                await asyncio.sleep(0.25)
            
            result = await process_query(query)
            search_docs.append(result)
        except Exception as e:
            # Handle exceptions gracefully
            print(f"Error processing query '{query}': {str(e)}")
            # Add a placeholder result for failed queries to maintain index alignment
            search_docs.append({
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": [],
                "error": str(e)
            })
            
            # Add additional delay if we hit a rate limit error
            if "429" in str(e):
                print("Rate limit exceeded. Adding additional delay...")
                await asyncio.sleep(1.0)  # Add a longer delay if we hit a rate limit
    
    return search_docs

@traceable
async def arxiv_search_async(search_queries, load_max_docs=5, get_full_documents=True, load_all_available_meta=True):
    """
    Performs concurrent searches on arXiv using the ArxivRetriever.

    Args:
        search_queries (List[str]): List of search queries or article IDs
        load_max_docs (int, optional): Maximum number of documents to return per query. Default is 5.
        get_full_documents (bool, optional): Whether to fetch full text of documents. Default is True.
        load_all_available_meta (bool, optional): Whether to load all available metadata. Default is True.

    Returns:
        List[dict]: List of search responses from arXiv, one per query. Each response has format:
            {
                'query': str,                    # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': [],
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the paper
                        'url': str,              # URL (Entry ID) of the paper
                        'content': str,          # Formatted summary with metadata
                        'score': float,          # Relevance score (approximated)
                        'raw_content': str|None  # Full paper content if available
                    },
                    ...
                ]
            }
    """
    
    async def process_single_query(query):
        try:
            # Create retriever for each query
            retriever = ArxivRetriever(
                load_max_docs=load_max_docs,
                get_full_documents=get_full_documents,
                load_all_available_meta=load_all_available_meta
            )
            
            # Run the synchronous retriever in a thread pool
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(None, lambda: retriever.invoke(query))
            
            results = []
            # Assign decreasing scores based on the order
            base_score = 1.0
            score_decrement = 1.0 / (len(docs) + 1) if docs else 0
            
            for i, doc in enumerate(docs):
                # Extract metadata
                metadata = doc.metadata
                
                # Use entry_id as the URL (this is the actual arxiv link)
                url = metadata.get('entry_id', '')
                
                # Format content with all useful metadata
                content_parts = []

                # Primary information
                if 'Summary' in metadata:
                    content_parts.append(f"Summary: {metadata['Summary']}")

                if 'Authors' in metadata:
                    content_parts.append(f"Authors: {metadata['Authors']}")

                # Add publication information
                published = metadata.get('Published')
                published_str = published.isoformat() if hasattr(published, 'isoformat') else str(published) if published else ''
                if published_str:
                    content_parts.append(f"Published: {published_str}")

                # Add additional metadata if available
                if 'primary_category' in metadata:
                    content_parts.append(f"Primary Category: {metadata['primary_category']}")

                if 'categories' in metadata and metadata['categories']:
                    content_parts.append(f"Categories: {', '.join(metadata['categories'])}")

                if 'comment' in metadata and metadata['comment']:
                    content_parts.append(f"Comment: {metadata['comment']}")

                if 'journal_ref' in metadata and metadata['journal_ref']:
                    content_parts.append(f"Journal Reference: {metadata['journal_ref']}")

                if 'doi' in metadata and metadata['doi']:
                    content_parts.append(f"DOI: {metadata['doi']}")

                # Get PDF link if available in the links
                pdf_link = ""
                if 'links' in metadata and metadata['links']:
                    for link in metadata['links']:
                        if 'pdf' in link:
                            pdf_link = link
                            content_parts.append(f"PDF: {pdf_link}")
                            break

                # Join all content parts with newlines 
                content = "\n".join(content_parts)
                
                result = {
                    'title': metadata.get('Title', ''),
                    'url': url,  # Using entry_id as the URL
                    'content': content,
                    'score': base_score - (i * score_decrement),
                    'raw_content': doc.page_content if get_full_documents else None
                }
                results.append(result)
                
            return {
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': results
            }
        except Exception as e:
            # Handle exceptions gracefully
            print(f"Error processing arXiv query '{query}': {str(e)}")
            return {
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': [],
                'error': str(e)
            }
    
    # Process queries sequentially with delay to respect arXiv rate limit (1 request per 3 seconds)
    search_docs = []
    for i, query in enumerate(search_queries):
        try:
            # Add delay between requests (3 seconds per ArXiv's rate limit)
            if i > 0:  # Don't delay the first request
                await asyncio.sleep(3.0)
            
            result = await process_single_query(query)
            search_docs.append(result)
        except Exception as e:
            # Handle exceptions gracefully
            print(f"Error processing arXiv query '{query}': {str(e)}")
            search_docs.append({
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': [],
                'error': str(e)
            })
            
            # Add additional delay if we hit a rate limit error
            if "429" in str(e) or "Too Many Requests" in str(e):
                print("ArXiv rate limit exceeded. Adding additional delay...")
                await asyncio.sleep(5.0)  # Add a longer delay if we hit a rate limit
    
    return search_docs

@traceable
async def pubmed_search_async(search_queries, top_k_results=5, email=None, api_key=None, doc_content_chars_max=4000):
    """
    Performs concurrent searches on PubMed using the PubMedAPIWrapper.

    Args:
        search_queries (List[str]): List of search queries
        top_k_results (int, optional): Maximum number of documents to return per query. Default is 5.
        email (str, optional): Email address for PubMed API. Required by NCBI.
        api_key (str, optional): API key for PubMed API for higher rate limits.
        doc_content_chars_max (int, optional): Maximum characters for document content. Default is 4000.

    Returns:
        List[dict]: List of search responses from PubMed, one per query. Each response has format:
            {
                'query': str,                    # The original search query
                'follow_up_questions': None,      
                'answer': None,
                'images': [],
                'results': [                     # List of search results
                    {
                        'title': str,            # Title of the paper
                        'url': str,              # URL to the paper on PubMed
                        'content': str,          # Formatted summary with metadata
                        'score': float,          # Relevance score (approximated)
                        'raw_content': str       # Full abstract content
                    },
                    ...
                ]
            }
    """
    
    async def process_single_query(query):
        try:
            # print(f"Processing PubMed query: '{query}'")
            
            # Create PubMed wrapper for the query
            wrapper = PubMedAPIWrapper(
                top_k_results=top_k_results,
                doc_content_chars_max=doc_content_chars_max,
                email=email if email else "your_email@example.com",
                api_key=api_key if api_key else ""
            )
            
            # Run the synchronous wrapper in a thread pool
            loop = asyncio.get_event_loop()
            
            # Use wrapper.lazy_load instead of load to get better visibility
            docs = await loop.run_in_executor(None, lambda: list(wrapper.lazy_load(query)))
            
            print(f"Query '{query}' returned {len(docs)} results")
            
            results = []
            # Assign decreasing scores based on the order
            base_score = 1.0
            score_decrement = 1.0 / (len(docs) + 1) if docs else 0
            
            for i, doc in enumerate(docs):
                # Format content with metadata
                content_parts = []
                
                if doc.get('Published'):
                    content_parts.append(f"Published: {doc['Published']}")
                
                if doc.get('Copyright Information'):
                    content_parts.append(f"Copyright Information: {doc['Copyright Information']}")
                
                if doc.get('Summary'):
                    content_parts.append(f"Summary: {doc['Summary']}")
                
                # Generate PubMed URL from the article UID
                uid = doc.get('uid', '')
                url = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/" if uid else ""
                
                # Join all content parts with newlines
                content = "\n".join(content_parts)
                
                result = {
                    'title': doc.get('Title', ''),
                    'url': url,
                    'content': content,
                    'score': base_score - (i * score_decrement),
                    'raw_content': doc.get('Summary', '')
                }
                results.append(result)
            
            return {
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': results
            }
        except Exception as e:
            # Handle exceptions with more detailed information
            error_msg = f"Error processing PubMed query '{query}': {str(e)}"
            print(error_msg)
            import traceback
            print(traceback.format_exc())  # Print full traceback for debugging
            
            return {
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': [],
                'error': str(e)
            }
    
    # Process all queries with a reasonable delay between them
    search_docs = []
    
    # Start with a small delay that increases if we encounter rate limiting
    delay = 1.0  # Start with a more conservative delay
    
    for i, query in enumerate(search_queries):
        try:
            # Add delay between requests
            if i > 0:  # Don't delay the first request
                # print(f"Waiting {delay} seconds before next query...")
                await asyncio.sleep(delay)
            
            result = await process_single_query(query)
            search_docs.append(result)
            
            # If query was successful with results, we can slightly reduce delay (but not below minimum)
            if result.get('results') and len(result['results']) > 0:
                delay = max(0.5, delay * 0.9)  # Don't go below 0.5 seconds
            
        except Exception as e:
            # Handle exceptions gracefully
            error_msg = f"Error in main loop processing PubMed query '{query}': {str(e)}"
            print(error_msg)
            
            search_docs.append({
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': [],
                'error': str(e)
            })
            
            # If we hit an exception, increase delay for next query
            delay = min(5.0, delay * 1.5)  # Don't exceed 5 seconds
    
    return search_docs

@traceable
async def linkup_search(search_queries, depth: Optional[str] = "standard"):
    """
    Performs concurrent web searches using the Linkup API.

    Args:
        search_queries (List[SearchQuery]): List of search queries to process
        depth (str, optional): "standard" (default)  or "deep". More details here https://docs.linkup.so/pages/documentation/get-started/concepts

    Returns:
        List[dict]: List of search responses from Linkup API, one per query. Each response has format:
            {
                'results': [            # List of search results
                    {
                        'title': str,   # Title of the search result
                        'url': str,     # URL of the result
                        'content': str, # Summary/snippet of content
                    },
                    ...
                ]
            }
    """
    client = LinkupClient()
    search_tasks = []
    for query in search_queries:
        search_tasks.append(
                client.async_search(
                    query,
                    depth,
                    output_type="searchResults",
                )
            )

    search_results = []
    for response in await asyncio.gather(*search_tasks):
        search_results.append(
            {
                "results": [
                    {"title": result.name, "url": result.url, "content": result.content}
                    for result in response.results
                ],
            }
        )

    return search_results

@traceable
async def google_search_async(search_queries: Union[str, List[str]], max_results: int = 5, include_raw_content: bool = True):
    """
    Performs concurrent web searches using Google.
    Uses Google Custom Search API if environment variables are set, otherwise falls back to web scraping.

    Args:
        search_queries (List[str]): List of search queries to process
        max_results (int): Maximum number of results to return per query
        include_raw_content (bool): Whether to fetch full page content

    Returns:
        List[dict]: List of search responses from Google, one per query
    """


    # Check for API credentials from environment variables
    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    use_api = bool(api_key and cx)
    
    # Handle case where search_queries is a single string
    if isinstance(search_queries, str):
        search_queries = [search_queries]
    
    # Define user agent generator
    def get_useragent():
        """Generates a random user agent string."""
        lynx_version = f"Lynx/{random.randint(2, 3)}.{random.randint(8, 9)}.{random.randint(0, 2)}"
        libwww_version = f"libwww-FM/{random.randint(2, 3)}.{random.randint(13, 15)}"
        ssl_mm_version = f"SSL-MM/{random.randint(1, 2)}.{random.randint(3, 5)}"
        openssl_version = f"OpenSSL/{random.randint(1, 3)}.{random.randint(0, 4)}.{random.randint(0, 9)}"
        return f"{lynx_version} {libwww_version} {ssl_mm_version} {openssl_version}"
    
    # Create executor for running synchronous operations
    executor = None if use_api else concurrent.futures.ThreadPoolExecutor(max_workers=5)
    
    # Use a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(5 if use_api else 2)
    
    async def search_single_query(query):
        async with semaphore:
            try:
                results = []
                
                # API-based search
                if use_api:
                    # The API returns up to 10 results per request
                    for start_index in range(1, max_results + 1, 10):
                        # Calculate how many results to request in this batch
                        num = min(10, max_results - (start_index - 1))
                        
                        # Make request to Google Custom Search API
                        params = {
                            'q': query,
                            'key': api_key,
                            'cx': cx,
                            'start': start_index,
                            'num': num
                        }
                        print(f"Requesting {num} results for '{query}' from Google API...")

                        async with aiohttp.ClientSession() as session:
                            async with session.get('https://www.googleapis.com/customsearch/v1', params=params) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    print(f"API error: {response.status}, {error_text}")
                                    break
                                    
                                data = await response.json()
                                
                                # Process search results
                                for item in data.get('items', []):
                                    result = {
                                        "title": item.get('title', ''),
                                        "url": item.get('link', ''),
                                        "content": item.get('snippet', ''),
                                        "score": None,
                                        "raw_content": item.get('snippet', '')
                                    }
                                    results.append(result)
                        
                        # Respect API quota with a small delay
                        await asyncio.sleep(0.2)
                        
                        # If we didn't get a full page of results, no need to request more
                        if not data.get('items') or len(data.get('items', [])) < num:
                            break
                
                # Web scraping based search
                else:
                    # Add delay between requests
                    await asyncio.sleep(0.5 + random.random() * 1.5)
                    print(f"Scraping Google for '{query}'...")

                    # Define scraping function
                    def google_search(query, max_results):
                        try:
                            lang = "en"
                            safe = "active"
                            start = 0
                            fetched_results = 0
                            fetched_links = set()
                            search_results = []
                            
                            while fetched_results < max_results:
                                # Send request to Google
                                resp = requests.get(
                                    url="https://www.google.com/search",
                                    headers={
                                        "User-Agent": get_useragent(),
                                        "Accept": "*/*"
                                    },
                                    params={
                                        "q": query,
                                        "num": max_results + 2,
                                        "hl": lang,
                                        "start": start,
                                        "safe": safe,
                                    },
                                    cookies = {
                                        'CONSENT': 'PENDING+987',  # Bypasses the consent page
                                        'SOCS': 'CAESHAgBEhIaAB',
                                    }
                                )
                                resp.raise_for_status()
                                
                                # Parse results
                                soup = BeautifulSoup(resp.text, "html.parser")
                                result_block = soup.find_all("div", class_="ezO2md")
                                new_results = 0
                                
                                for result in result_block:
                                    link_tag = result.find("a", href=True)
                                    title_tag = link_tag.find("span", class_="CVA68e") if link_tag else None
                                    description_tag = result.find("span", class_="FrIlee")
                                    
                                    if link_tag and title_tag and description_tag:
                                        link = unquote(link_tag["href"].split("&")[0].replace("/url?q=", ""))
                                        
                                        if link in fetched_links:
                                            continue
                                        
                                        fetched_links.add(link)
                                        title = title_tag.text
                                        description = description_tag.text
                                        
                                        # Store result in the same format as the API results
                                        search_results.append({
                                            "title": title,
                                            "url": link,
                                            "content": description,
                                            "score": None,
                                            "raw_content": description
                                        })
                                        
                                        fetched_results += 1
                                        new_results += 1
                                        
                                        if fetched_results >= max_results:
                                            break
                                
                                if new_results == 0:
                                    break
                                    
                                start += 10
                                time.sleep(1)  # Delay between pages
                            
                            return search_results
                                
                        except Exception as e:
                            print(f"Error in Google search for '{query}': {str(e)}")
                            return []
                    
                    # Execute search in thread pool
                    loop = asyncio.get_running_loop()
                    search_results = await loop.run_in_executor(
                        executor, 
                        lambda: google_search(query, max_results)
                    )
                    
                    # Process the results
                    results = search_results
                
                # If requested, fetch full page content asynchronously (for both API and web scraping)
                if include_raw_content and results:
                    content_semaphore = asyncio.Semaphore(3)
                    
                    async with aiohttp.ClientSession() as session:
                        fetch_tasks = []
                        
                        async def fetch_full_content(result):
                            async with content_semaphore:
                                url = result['url']
                                headers = {
                                    'User-Agent': get_useragent(),
                                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                                }
                                
                                try:
                                    await asyncio.sleep(0.2 + random.random() * 0.6)
                                    async with session.get(url, headers=headers, timeout=10) as response:
                                        if response.status == 200:
                                            # Check content type to handle binary files
                                            content_type = response.headers.get('Content-Type', '').lower()
                                            
                                            # Handle PDFs and other binary files
                                            if 'application/pdf' in content_type or 'application/octet-stream' in content_type:
                                                # For PDFs, indicate that content is binary and not parsed
                                                result['raw_content'] = f"[Binary content: {content_type}. Content extraction not supported for this file type.]"
                                            else:
                                                try:
                                                    # Try to decode as UTF-8 with replacements for non-UTF8 characters
                                                    html = await response.text(errors='replace')
                                                    soup = BeautifulSoup(html, 'html.parser')
                                                    result['raw_content'] = soup.get_text()
                                                except UnicodeDecodeError as ude:
                                                    # Fallback if we still have decoding issues
                                                    result['raw_content'] = f"[Could not decode content: {str(ude)}]"
                                except Exception as e:
                                    print(f"Warning: Failed to fetch content for {url}: {str(e)}")
                                    result['raw_content'] = f"[Error fetching content: {str(e)}]"
                                return result
                        
                        for result in results:
                            fetch_tasks.append(fetch_full_content(result))
                        
                        updated_results = await asyncio.gather(*fetch_tasks)
                        results = updated_results
                        print(f"Fetched full content for {len(results)} results")
                
                return {
                    "query": query,
                    "follow_up_questions": None,
                    "answer": None,
                    "images": [],
                    "results": results
                }
            except Exception as e:
                print(f"Error in Google search for query '{query}': {str(e)}")
                return {
                    "query": query,
                    "follow_up_questions": None,
                    "answer": None,
                    "images": [],
                    "results": []
                }
    
    try:
        # Create tasks for all search queries
        search_tasks = [search_single_query(query) for query in search_queries]
        
        # Execute all searches concurrently
        search_results = await asyncio.gather(*search_tasks)
        
        return search_results
    finally:
        # Only shut down executor if it was created
        if executor:
            executor.shutdown(wait=False)

async def scrape_pages(titles: List[str], urls: List[str]) -> str:
    """
    Scrapes content from a list of URLs and formats it into a readable markdown document.
    
    This function:
    1. Takes a list of page titles and URLs
    2. Makes asynchronous HTTP requests to each URL
    3. Converts HTML content to markdown
    4. Formats all content with clear source attribution
    
    Args:
        titles (List[str]): A list of page titles corresponding to each URL
        urls (List[str]): A list of URLs to scrape content from
        
    Returns:
        str: A formatted string containing the full content of each page in markdown format,
             with clear section dividers and source attribution
    """
    
    # Create an async HTTP client
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        pages = []
        
        # Fetch each URL and convert to markdown
        for url in urls:
            try:
                # Fetch the content
                response = await client.get(url)
                response.raise_for_status()
                
                # Convert HTML to markdown if successful
                if response.status_code == 200:
                    # Handle different content types
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type:
                        # Convert HTML to markdown
                        markdown_content = markdownify(response.text)
                        pages.append(markdown_content)
                    else:
                        # For non-HTML content, just mention the content type
                        pages.append(f"Content type: {content_type} (not converted to markdown)")
                else:
                    pages.append(f"Error: Received status code {response.status_code}")
        
            except Exception as e:
                # Handle any exceptions during fetch
                pages.append(f"Error fetching URL: {str(e)}")
        
        # Create formatted output
        formatted_output = f"Search results: \n\n"
        
        for i, (title, url, page) in enumerate(zip(titles, urls, pages)):
            formatted_output += f"\n\n--- SOURCE {i+1}: {title} ---\n"
            formatted_output += f"URL: {url}\n\n"
            formatted_output += f"FULL CONTENT:\n {page}"
            formatted_output += "\n\n" + "-" * 80 + "\n"
        
    return formatted_output

@tool
async def duckduckgo_search(search_queries: List[str]):
    """Perform searches using DuckDuckGo with retry logic to handle rate limits
    
    Args:
        search_queries (List[str]): List of search queries to process
        
    Returns:
        str: A formatted string of search results
    """
    
    async def process_single_query(query):
        # Execute synchronous search in the event loop's thread pool
        loop = asyncio.get_event_loop()
        
        def perform_search():
            max_retries = 3
            retry_count = 0
            backoff_factor = 2.0
            last_exception = None
            
            while retry_count <= max_retries:
                try:
                    results = []
                    with DDGS() as ddgs:
                        # Change query slightly and add delay between retries
                        if retry_count > 0:
                            # Random delay with exponential backoff
                            delay = backoff_factor ** retry_count + random.random()
                            print(f"Retry {retry_count}/{max_retries} for query '{query}' after {delay:.2f}s delay")
                            time.sleep(delay)
                            
                            # Add a random element to the query to bypass caching/rate limits
                            modifiers = ['about', 'info', 'guide', 'overview', 'details', 'explained']
                            modified_query = f"{query} {random.choice(modifiers)}"
                        else:
                            modified_query = query
                        
                        # Execute search
                        ddg_results = list(ddgs.text(modified_query, max_results=5))
                        
                        # Format results
                        for i, result in enumerate(ddg_results):
                            results.append({
                                'title': result.get('title', ''),
                                'url': result.get('href', ''),
                                'content': result.get('body', ''),
                                'score': 1.0 - (i * 0.1),  # Simple scoring mechanism
                                'raw_content': result.get('body', '')
                            })
                        
                        # Return successful results
                        return {
                            'query': query,
                            'follow_up_questions': None,
                            'answer': None,
                            'images': [],
                            'results': results
                        }
                except Exception as e:
                    # Store the exception and retry
                    last_exception = e
                    retry_count += 1
                    print(f"DuckDuckGo search error: {str(e)}. Retrying {retry_count}/{max_retries}")
                    
                    # If not a rate limit error, don't retry
                    if "Ratelimit" not in str(e) and retry_count >= 1:
                        print(f"Non-rate limit error, stopping retries: {str(e)}")
                        break
            
            # If we reach here, all retries failed
            print(f"All retries failed for query '{query}': {str(last_exception)}")
            # Return empty results but with query info preserved
            return {
                'query': query,
                'follow_up_questions': None,
                'answer': None,
                'images': [],
                'results': [],
                'error': str(last_exception)
            }
            
        return await loop.run_in_executor(None, perform_search)

    # Process queries with delay between them to reduce rate limiting
    search_docs = []
    urls = []
    titles = []
    for i, query in enumerate(search_queries):
        # Add delay between queries (except first one)
        if i > 0:
            delay = 2.0 + random.random() * 2.0  # Random delay 2-4 seconds
            await asyncio.sleep(delay)
        
        # Process the query
        result = await process_single_query(query)
        search_docs.append(result)
        
        # Safely extract URLs and titles from results, handling empty result cases
        if result['results'] and len(result['results']) > 0:
            for res in result['results']:
                if 'url' in res and 'title' in res:
                    urls.append(res['url'])
                    titles.append(res['title'])
    
    # If we got any valid URLs, scrape the pages
    if urls:
        return await scrape_pages(titles, urls)
    else:
        return "No valid search results found. Please try different search queries or use a different search API."

TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)

@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    include_raw_content: bool = True,
    config: RunnableConfig = None
) -> str:
    """
    Fetches results from Tavily search API.

    Args:
        queries (List[str]): List of search queries
        max_results (int): Maximum number of results to return
        topic (Literal['general', 'news', 'finance']): Topic to filter results by

    Returns:
        str: A formatted string of search results
    """
    # Use tavily_search_async with include_raw_content=True to get content directly
    search_results = await tavily_search_async(
        queries,
        max_results=max_results,
        topic=topic,
        include_raw_content=include_raw_content
    )

    # Format the search results directly using the raw_content already provided
    formatted_output = f"Search results: \n\n"
    
    # Deduplicate results by URL
    unique_results = {}
    for response in search_results:
        for result in response['results']:
            url = result['url']
            if url not in unique_results:
                unique_results[url] = {**result, "query": response['query']}

    async def noop():
        return None

    configurable = WorkflowConfiguration.from_runnable_config(config)
    max_char_to_include = 30_000
    # TODO: share this behavior across all search implementations / tools
    if configurable.process_search_results == "summarize":
        if configurable.summarization_model_provider == "anthropic":
            extra_kwargs = {"betas": ["extended-cache-ttl-2025-04-11"]}
        else:
            extra_kwargs = {}

        summarization_model = init_chat_model(
            model=configurable.summarization_model,
            model_provider=configurable.summarization_model_provider,
            max_retries=configurable.max_structured_output_retries,
            **extra_kwargs
        )
        summarization_tasks = [
            noop() if not result.get("raw_content") else summarize_webpage(summarization_model, result['raw_content'][:max_char_to_include])
            for result in unique_results.values()
        ]
        summaries = await asyncio.gather(*summarization_tasks)
        unique_results = {
            url: {'title': result['title'], 'content': result['content'] if summary is None else summary}
            for url, result, summary in zip(unique_results.keys(), unique_results.values(), summaries)
        }
    elif configurable.process_search_results == "split_and_rerank":
        embeddings = init_embeddings("openai:text-embedding-3-small")
        results_by_query = itertools.groupby(unique_results.values(), key=lambda x: x['query'])
        all_retrieved_docs = []
        for query, query_results in results_by_query:
            query_results_list = list(query_results)
            max_chunks = 2 * len(query_results_list) # 两倍于查询结果数量
            retrieved_docs = await split_and_rerank_search_results(embeddings, query, query_results_list, max_chunks=max_chunks)
            all_retrieved_docs.extend(retrieved_docs)

        stitched_docs = stitch_documents_by_url(all_retrieved_docs)
        unique_results = {
            doc.metadata['url']: {'title': doc.metadata['title'], 'content': doc.page_content}
            for doc in stitched_docs
        }

    # Format the unique results
    for i, (url, result) in enumerate(unique_results.items()):
        formatted_output += f"\n\n--- SOURCE {i+1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        if result.get('raw_content'):
            formatted_output += f"FULL CONTENT:\n{result['raw_content'][:max_char_to_include]}"  # Limit content size
        formatted_output += "\n\n" + "-" * 80 + "\n"
    
    if unique_results:
        return formatted_output
    else:
        return "No valid search results found. Please try different search queries or use a different search API."


@tool
async def azureaisearch_search(queries: List[str], max_results: int = 5, topic: str = "general") -> str:
    """
    Fetches results from Azure AI Search API.
    
    Args:
        queries (List[str]): List of search queries
        
    Returns:
        str: A formatted string of search results
    """
    # Use azureaisearch_search_async with include_raw_content=True to get content directly
    search_results = await azureaisearch_search_async(
        queries,
        max_results=max_results,
        topic=topic,
        include_raw_content=True
    )

    # Format the search results directly using the raw_content already provided
    formatted_output = f"Search results: \n\n"
    
    # Deduplicate results by URL
    unique_results = {}
    for response in search_results:
        for result in response['results']:
            url = result['url']
            if url not in unique_results:
                unique_results[url] = result
    
    # Format the unique results
    for i, (url, result) in enumerate(unique_results.items()):
        formatted_output += f"\n\n--- SOURCE {i+1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        if result.get('raw_content'):
            formatted_output += f"FULL CONTENT:\n{result['raw_content'][:30000]}"  # Limit content size
        formatted_output += "\n\n" + "-" * 80 + "\n"
    
    if unique_results:
        return formatted_output
    else:
        return "No valid search results found. Please try different search queries or use a different search API."


async def select_and_execute_search(search_api: str, query_list: list[str], params_to_pass: dict, include_raw_content: bool = True) -> str:
    """Select and execute the appropriate search API.
    
    Args:
        search_api: Name of the search API to use
        query_list: List of search queries to execute
        params_to_pass: Parameters to pass to the search API
        
    Returns:
        Formatted string containing search results
        
    Raises:
        ValueError: If an unsupported search API is specified
    """
    if search_api == "tavily":
        # Tavily search tool used with both workflow and agent 
        # and returns a formatted source string
        return await tavily_search.ainvoke({'queries': query_list, 'include_raw_content': include_raw_content, **params_to_pass})
    elif search_api == "duckduckgo":
        # DuckDuckGo search tool used with both workflow and agent 
        return await duckduckgo_search.ainvoke({'search_queries': query_list})
    elif search_api == "perplexity":
        search_results = perplexity_search(query_list, **params_to_pass)
    elif search_api == "exa":
        search_results = await exa_search(query_list, **params_to_pass)
    elif search_api == "arxiv":
        search_results = await arxiv_search_async(query_list, **params_to_pass)
    elif search_api == "pubmed":
        search_results = await pubmed_search_async(query_list, **params_to_pass)
    elif search_api == "linkup":
        search_results = await linkup_search(query_list, **params_to_pass)
    elif search_api == "googlesearch":
        search_results = await google_search_async(query_list, **params_to_pass)
    elif search_api == "azureaisearch":
        search_results = await azureaisearch_search_async(query_list, **params_to_pass)
    else:
        raise ValueError(f"Unsupported search API: {search_api}")

    return deduplicate_and_format_sources(search_results, max_tokens_per_source=4000, deduplication_strategy="keep_first")


class Summary(BaseModel):
    summary: str
    key_excerpts: list[str]


async def summarize_webpage(model: BaseChatModel, webpage_content: str) -> str:
    """Summarize webpage content."""

    SUMMARIZATION_PROMPT = "TODO"
    try:
        user_input_content = "Please summarize the article"
        if isinstance(model, ChatAnthropic):
            user_input_content = [{
                "type": "text",
                "text": user_input_content,
                "cache_control": {"type": "ephemeral", "ttl": "1h"}
            }]

        summary = await model.with_structured_output(Summary).with_retry(stop_after_attempt=2).ainvoke([
            {"role": "system", "content": SUMMARIZATION_PROMPT.format(webpage_content=webpage_content)},
            {"role": "user", "content": user_input_content},
        ])
    except:
        # fall back on the raw content
        return webpage_content

    def format_summary(summary: Summary):
        excerpts_str = "\n".join(f'- {e}' for e in summary.key_excerpts)
        return f"""<summary>\n{summary.summary}\n</summary>\n\n<key_excerpts>\n{excerpts_str}\n</key_excerpts>"""

    return format_summary(summary)


async def split_and_rerank_search_results(embeddings: Embeddings, query: str, search_results: list[dict], max_chunks: int = 5):
    """异步版本的分割和重排搜索结果函数，避免同步阻塞问题"""
    # 将网页内容分割成chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=200, add_start_index=True
    )
    documents = [
        Document(
            page_content=result.get('raw_content') or result['content'],
            metadata={"url": result['url'], "title": result['title']}
        )
        for result in search_results
    ]
    all_splits = text_splitter.split_documents(documents)
    print(f"Splitting {len(all_splits)} chunks for query: {query}")

    # 创建向量存储
    vector_store = InMemoryVectorStore(embeddings)
    
    # 分批添加文档以避免token限制，使用asyncio.to_thread避免阻塞
    # 估算每批处理的文档数量：每个chunk约1500字符，保守估计每个token约4字符
    # OpenAI限制300k tokens，为安全起见设置为200k tokens (约50个chunks)
    batch_size = 80
    
    for i in range(0, len(all_splits), batch_size):
        batch = all_splits[i:i + batch_size]
        try:
            # 使用 run_in_executor 将同步操作转为异步，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: vector_store.add_documents(documents=batch))
            print(f"Added {len(batch)} chunks to vector store")
        except Exception as e:
            # 如果批次仍然太大，进一步减小批次
            if "max_tokens_per_request" in str(e):
                # 尝试更小的批次大小
                smaller_batch_size = 50
                for j in range(i, min(i + batch_size, len(all_splits)), smaller_batch_size):
                    smaller_batch = all_splits[j:j + smaller_batch_size]
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, lambda: vector_store.add_documents(documents=smaller_batch))
                    except Exception as inner_e:
                        # 如果还是失败，跳过这批文档并记录警告
                        print(f"Warning: Skipped batch {j//smaller_batch_size + 1} due to token limit: {inner_e}")
                        continue
            else:
                # 如果是其他错误，重新抛出
                raise e

    # 检索相关chunks，同样使用异步方式避免阻塞
    loop = asyncio.get_event_loop()
    retrieved_docs = await loop.run_in_executor(None, lambda: vector_store.similarity_search(query, k=max_chunks))
    return retrieved_docs


def stitch_documents_by_url(documents: list[Document]) -> list[Document]:
    url_to_docs: defaultdict[str, list[Document]] = defaultdict(list)
    url_to_snippet_hashes: defaultdict[str, set[str]] = defaultdict(set)
    for doc in documents:
        snippet_hash = hashlib.sha256(doc.page_content.encode()).hexdigest()
        url = doc.metadata['url']
        # deduplicate snippets by the content
        if snippet_hash in url_to_snippet_hashes[url]:
            continue

        url_to_docs[url].append(doc)
        url_to_snippet_hashes[url].add(snippet_hash)

    # stitch retrieved chunks into a single doc per URL
    stitched_docs = []
    for docs in url_to_docs.values():
        stitched_doc = Document(
            page_content="\n\n".join([f"...{doc.page_content}..." for doc in docs]),
            metadata=cast(Document, docs[0]).metadata
        )
        stitched_docs.append(stitched_doc)

    return stitched_docs


def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.datetime.now().strftime("%a %b %-d, %Y")


async def load_mcp_server_config(path: str) -> dict:
    """Load MCP server configuration from a file."""

    def _load():
        with open(path, "r") as f:
            config = json.load(f)
        return config

    config = await asyncio.to_thread(_load)
    return config

def parse_position(position: str) -> List[int]:
    """
    解析位置编号为数字列表
    
    Args:
        position: 位置编号，如 "1", "2.1", "3.2.1"
        
    Returns:
        数字列表，如 [1], [2, 1], [3, 2, 1]
    """
    try:
        return [int(x) for x in position.split('.')]
    except ValueError:
        raise ValueError(f"Invalid position format: {position}")

def find_node_by_position(outline_nodes: List[OutlineNode], position: str) -> Optional[OutlineNode]:
    """
    根据位置编号查找节点
    
    Args:
        outline_nodes: 大纲节点列表
        position: 位置编号，如 "1", "2.1", "3.2.1"
        
    Returns:
        找到的节点，如果没找到返回None
    """
    try:
        path = parse_position(position)
        current_nodes = outline_nodes
        target_node = None
        
        for i, index in enumerate(path):
            # 获取当前层级的节点（1-based索引）
            if index < 1 or index > len(current_nodes):
                return None
            
            target_node = current_nodes[index - 1]  # 转换为0-based索引
            
            # 如果还有下一层，继续向下查找
            if i < len(path) - 1:
                current_nodes = target_node.children
        
        return target_node
    except (ValueError, IndexError):
        return None

def get_parent_and_index_by_position(outline_nodes: List[OutlineNode], position: str) -> Tuple[Optional[OutlineNode], List[OutlineNode], int]:
    """
    根据位置编号获取父节点、目标列表和插入索引
    
    Args:
        outline_nodes: 大纲节点列表
        position: 位置编号，如 "1", "2.1", "3.2.1"
        
    Returns:
        (父节点, 目标节点列表, 插入索引)
        父节点为None表示是顶层操作
    """
    try:
        path = parse_position(position)
        
        if len(path) == 1:
            # 顶层节点
            return None, outline_nodes, path[0] - 1  # 转换为0-based索引
        
        # 找到父节点
        parent_path = path[:-1]
        parent_position = '.'.join(str(x) for x in parent_path)
        parent_node = find_node_by_position(outline_nodes, parent_position)
        
        if parent_node is None:
            raise ValueError(f"Parent node not found for position: {position}")
        
        insert_index = path[-1] - 1  # 转换为0-based索引
        return parent_node, parent_node.children, insert_index
    
    except (ValueError, IndexError):
        raise ValueError(f"Invalid position: {position}")

def get_level_from_position(position: str) -> int:
    """
    根据位置编号推断节点层级
    
    Args:
        position: 位置编号，如 "1", "2.1", "3.2.1"
        
    Returns:
        节点层级 (1, 2, 或 3)
    """
    return len(position.split('.'))

def execute_position_based_adjustments(outline_nodes: List[OutlineNode], adjustments: List) -> List[OutlineNode]:
    """
    执行基于位置编号的大纲调整操作
    
    Args:
        outline_nodes: 大纲节点列表
        adjustments: 调整指令列表
        
    Returns:
        调整后的大纲节点列表
    """
    # 创建副本避免修改原始数据
    working_nodes = copy.deepcopy(outline_nodes)
    
    # 按操作类型分组处理：先删除，再修改，最后添加
    # 这样可以避免位置编号在操作过程中发生变化
    delete_ops = [adj for adj in adjustments if adj.action == "delete"]
    modify_ops = [adj for adj in adjustments if adj.action == "modify"]
    add_ops = [adj for adj in adjustments if adj.action == "add"]
    
    # 删除操作（按位置倒序执行，避免索引变化）
    delete_ops.sort(key=lambda x: x.position, reverse=True)
    for adjustment in delete_ops:
        try:
            _delete_node_by_position(working_nodes, adjustment.position)
        except Exception as e:
            print(f"Failed to delete node at position {adjustment.position}: {e}")
            continue
    
    # 修改操作
    for adjustment in modify_ops:
        try:
            _modify_node_by_position(working_nodes, adjustment.position, adjustment.new_title)
        except Exception as e:
            print(f"Failed to modify node at position {adjustment.position}: {e}")
            continue
    
    # 添加操作（按位置正序执行）
    add_ops.sort(key=lambda x: x.position)
    for adjustment in add_ops:
        try:
            _add_node_by_position(working_nodes, adjustment.position, adjustment.new_title)
        except Exception as e:
            print(f"Failed to add node at position {adjustment.position}: {e}")
            continue
    
    return working_nodes

def _delete_node_by_position(outline_nodes: List[OutlineNode], position: str):
    """删除指定位置的节点"""
    parent_node, target_list, index = get_parent_and_index_by_position(outline_nodes, position)
    
    if index < 0 or index >= len(target_list):
        raise ValueError(f"Invalid position: {position}")
    
    del target_list[index]

def _modify_node_by_position(outline_nodes: List[OutlineNode], position: str, new_title: Optional[str]):
    """修改指定位置的节点"""
    node = find_node_by_position(outline_nodes, position)
    
    if node is None:
        raise ValueError(f"Node not found at position: {position}")
    
    if new_title:
        node.title = new_title
        # 标记为需要重新处理，描述将由模型补充
        node.status = "pending"
        node.description = ""

def _add_node_by_position(outline_nodes: List[OutlineNode], position: str, title: Optional[str]):
    """在指定位置添加新节点"""
    parent_node, target_list, insert_index = get_parent_and_index_by_position(outline_nodes, position)
    level = get_level_from_position(position)
    
    # 创建新节点，描述为空，将由模型补充
    new_node = OutlineNode(
        title=title or "New Node",
        description="",  # 空描述，待模型补充
        level=level,
        children=[],
        status="pending"
    )
    
    # 插入到指定位置
    target_list.insert(insert_index, new_node)