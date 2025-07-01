"""Influflow"""

__version__ = "0.0.15"

# 导出AI模块的主要组件，保持向后兼容性
from .ai.state import Outline, OutlineNode, OutlineLeafNode, InfluflowState
from .ai.configuration import Configuration, WorkflowConfiguration

__all__ = [
    "Outline",
    "OutlineNode", 
    "OutlineLeafNode",
    "InfluflowState",
    "Configuration",
    "WorkflowConfiguration",
]