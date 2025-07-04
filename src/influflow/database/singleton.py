"""Supabase Client Singleton.

Supabase客户端单例模式实现
"""

import os
from typing import TYPE_CHECKING, Optional

# 类型检查时导入具体类型，运行时避免导入错误
if TYPE_CHECKING:
    from supabase import Client as SyncClient
else:
    SyncClient = None

# 模块级变量，用于缓存Supabase客户端实例
_supabase_client: Optional[SyncClient] = None

# 检查Supabase是否可用
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    create_client = None


def get_supabase_client() -> SyncClient:
    """获取Supabase客户端实例（单例模式）.
    
    使用单例模式确保只创建一个客户端实例，提高性能和资源利用率。
    
    Returns:
        Supabase客户端实例
        
    Raises:
        ValueError: 当环境变量缺失时
        ImportError: 当Supabase SDK未安装时
    """
    global _supabase_client
    
    # 如果已经有实例，直接返回
    if _supabase_client is not None:
        return _supabase_client
    
    # 检查Supabase是否可用
    if not SUPABASE_AVAILABLE or create_client is None:
        raise ImportError("Supabase SDK is not installed. Install with: pip install supabase")
    
    # 获取环境变量
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        raise ValueError("SUPABASE_URL environment variable is required")
    if not supabase_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")
    
    # 创建并缓存客户端实例
    _supabase_client = create_client(supabase_url, supabase_key)
    return _supabase_client
