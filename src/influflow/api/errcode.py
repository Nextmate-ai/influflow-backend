"""
错误码定义模块
简化的错误码系统，只保留成功和内部错误两种状态
"""

from enum import Enum


class ErrorCodes(Enum):
    """业务错误码枚举"""
    
    # 成功状态
    SUCCESS = (10000, "Success")
    
    # 内部错误
    INTERNAL_ERROR = (50000, "Internal server error")
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
