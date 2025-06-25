import os
from enum import Enum
from dataclasses import dataclass, fields, field
from typing import Any, Optional, Dict, Literal

from langchain_core.runnables import RunnableConfig

DEFAULT_REPORT_STRUCTURE = """Use this structure to create a report on the user-provided topic:

1. TL;DR (no research needed)
   - 1-2 sentences summary of the topic or answer to the user's question

2. Main Body Sections:
   - Each section should focus on a sub-topic of the user-provided topic
   
3. Conclusion (no research needed)
   - Aim for 1 structural element (either a list or table) that distills the main body sections 
   - Provide a concise summary of the report"""

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
    """Configuration for the workflow/graph-based implementation (graph.py)."""
    # Common configuration
    report_structure: str = DEFAULT_REPORT_STRUCTURE
    search_api: SearchAPI = SearchAPI.TAVILY
    search_api_config: Optional[Dict[str, Any]] = field(default_factory=lambda: {"max_results": 5})
    process_search_results: Literal["summarize", "split_and_rerank"] | None = "split_and_rerank"
    summarization_model_provider: str = "openai"
    summarization_model: str = "gpt-4o-mini"
    max_structured_output_retries: int = 3
    include_source_str: bool = False
    
    # Workflow-specific configuration
    number_of_queries: int = 2 # Number of search queries to generate per iteration
    max_search_depth: int = 1 # Maximum number of reflection + search iterations
    planner_provider: str = "openai"
    planner_model: str = "gpt-4.1-mini"
    planner_model_kwargs: Optional[Dict[str, Any]] = field(default_factory=lambda: {"temperature": 0.2})
    writer_provider: str = "openai"
    writer_model: str = "gpt-4.1-mini"
    writer_model_kwargs: Optional[Dict[str, Any]] = field(default_factory=lambda: {"temperature": 0.5})
    styler_provider: str = "openai"
    styler_model: str = "gpt-4.1-mini"
    styler_model_kwargs: Optional[Dict[str, Any]] = field(default_factory=lambda: {"temperature": 0.5})

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
        return cls(**{k: v for k, v in values.items() if v})

# Keep the old Configuration class for backward compatibility
Configuration = WorkflowConfiguration
