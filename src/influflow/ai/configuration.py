import os
from enum import Enum
from dataclasses import dataclass, fields, field
from typing import Any, Optional, Dict, Literal

from langchain_core.runnables import RunnableConfig

class SearchAPI(Enum):
    """搜索API枚举 - 当前项目暂不使用搜索功能"""
    NONE = "none"

@dataclass(kw_only=True)
class WorkflowConfiguration:
    """Configuration for the influflow Twitter thread generation workflow."""
    
    # Search configuration - 暂时保留配置结构，但不启用搜索功能
    search_api: SearchAPI = SearchAPI.NONE
    search_api_config: Optional[Dict[str, Any]] = field(default_factory=lambda: {"max_results": 5})
    process_search_results: Literal["summarize", "split_and_rerank"] | None = None
    
    # Model configuration
    number_of_queries: int = 3  # 增加查询数量以获得更丰富的内容
    writer_provider: str = "openai"
    writer_model: str = "gpt-4.1"
    writer_model_kwargs: Optional[Dict[str, Any]] = None  # 提高创造性
    writer_temperature: float = 0.7

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
