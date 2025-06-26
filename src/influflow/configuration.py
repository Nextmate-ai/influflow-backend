import os
from enum import Enum
from dataclasses import dataclass, fields, field
from typing import Any, Optional, Dict, Literal

from langchain_core.runnables import RunnableConfig
from influflow.prompt import DEFAULT_TWITTER_THREAD_STRUCTURE

class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    EXA = "exa"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    LINKUP = "linkup"
    DUCKDUCKGO = "duckduckgo"
    GOOGLESEARCH = "googlesearch"
    NONE = "none"

@dataclass(kw_only=True)
class WorkflowConfiguration:
    """Configuration for the influflow Twitter thread generation workflow."""
    
    # Twitter thread specific configuration
    thread_structure: str = DEFAULT_TWITTER_THREAD_STRUCTURE
    max_thread_length: int = 15  # 最大tweet数量
    min_thread_length: int = 5   # 最小tweet数量
    max_outline_depth: int = 3   # 大纲最大层级
    
    # Search configuration
    search_api: SearchAPI = SearchAPI.TAVILY
    search_api_config: Optional[Dict[str, Any]] = field(default_factory=lambda: {"max_results": 5})
    process_search_results: Literal["summarize", "split_and_rerank"] | None = "split_and_rerank"
    
    # Model configuration
    number_of_queries: int = 3  # 增加查询数量以获得更丰富的内容
    planner_provider: str = "openai"
    planner_model: str = "gpt-4.1-mini"  # 使用更经济的模型作为默认
    planner_model_kwargs: Optional[Dict[str, Any]] = field(default_factory=lambda: {"temperature": 0.3})
    writer_provider: str = "openai"
    writer_model: str = "gpt-4.1-mini"
    writer_model_kwargs: Optional[Dict[str, Any]] = field(default_factory=lambda: {"temperature": 0.7})  # 提高创造性
    
    # Twitter content specific settings
    enforce_character_limit: bool = True  # 是否严格执行280字符限制
    include_hashtags: bool = True         # 是否包含hashtag建议
    include_emojis: bool = True          # 是否使用emoji
    thread_numbering: bool = True        # 是否添加thread编号 (1/n, 2/n)
    
    # Advanced settings
    max_structured_output_retries: int = 3
    include_source_str: bool = False
    summarization_model_provider: str = "openai"
    summarization_model: str = "gpt-4o-mini"

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "WorkflowConfiguration":
        """Create a WorkflowConfiguration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }
        # 过滤掉None值
        filtered_values = {k: v for k, v in values.items() if v is not None}
        return cls(**filtered_values)

# Keep the old Configuration class for backward compatibility
Configuration = WorkflowConfiguration
