"""
FastAPI 认证依赖系统
基于 Dependencies 的最佳实践实现，替代 Middleware 方案
"""

import os
import jwt
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from supabase import create_client, Client

from influflow.api.errcode import ErrorCodes
from influflow.api.models import build_error_response


class AuthenticationError(HTTPException):
    """自定义认证异常，返回统一的错误响应格式"""
    
    def __init__(self, message: str, code: int = ErrorCodes.UNAUTHORIZED.code):
        # 创建统一的错误响应
        error_response = build_error_response(message=message, code=code)
        # 设置 HTTPException 的 detail 为完整的错误响应
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response.model_dump(),  # 转换为字典格式
            headers={"WWW-Authenticate": "Bearer"}
        )


# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


class AuthService:
    """认证服务类，处理 Supabase JWT 令牌验证"""
    
    def __init__(self):
        """初始化认证服务"""
        # 初始化 Supabase 客户端
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role key
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required")
            
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT 令牌并获取用户信息
        
        Args:
            token: JWT 令牌字符串
            
        Returns:
            用户信息字典，如果验证失败则返回 None
        """
        try:
            # 使用 Supabase 客户端验证 JWT 令牌
            response = self.supabase.auth.get_user(token)
            
            if response and hasattr(response, 'user') and response.user:
                user = response.user
                # 返回标准化的用户信息
                return {
                    "sub": user.id,  # 用户 ID，JWT 标准字段
                    "email": getattr(user, 'email', ''),
                    "user_metadata": getattr(user, 'user_metadata', {}),
                    "app_metadata": getattr(user, 'app_metadata', {}),
                    "aud": "authenticated",  # Supabase 标准 audience
                    "role": "authenticated"  # Supabase 标准角色
                }
            else:
                print("Supabase auth.get_user returned no user")
                return None
                
        except Exception as e:
            print(f"Supabase JWT verification error: {e}")
            
            # 备用方案：手动解码 JWT（需要 JWT secret）
            try:
                jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
                if not jwt_secret:
                    print("Warning: SUPABASE_JWT_SECRET not set, cannot verify JWT manually")
                    return None
                
                # 手动解码 JWT，这是 Supabase JWT 的标准格式
                payload = jwt.decode(
                    token, 
                    jwt_secret, 
                    algorithms=["HS256"],
                    audience="authenticated"
                )
                
                # 返回 JWT 载荷中的标准字段
                return {
                    "sub": payload.get("sub"),  # 用户 ID
                    "email": payload.get("email", ""),
                    "aud": payload.get("aud", "authenticated"),
                    "role": payload.get("role", "authenticated"),
                    "user_metadata": payload.get("user_metadata", {}),
                    "app_metadata": payload.get("app_metadata", {})
                }
                
            except jwt.InvalidTokenError as jwt_error:
                print(f"JWT decode error: {jwt_error}")
                return None
            except Exception as manual_error:
                print(f"Manual JWT verification error: {manual_error}")
                return None


# 全局认证服务实例
auth_service = AuthService()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """获取当前认证用户信息的依赖函数
    
    Args:
        credentials: HTTP Bearer 认证凭据
        
    Returns:
        用户信息字典
        
    Raises:
        AuthenticationError: 当认证失败时，返回统一的错误响应格式
    """
    if not credentials:
        raise AuthenticationError(
            message="Authorization token is required",
            code=ErrorCodes.UNAUTHORIZED.code
        )
    
    # 验证 JWT 令牌
    user_info = await auth_service.verify_token(credentials.credentials)
    
    if not user_info:
        raise AuthenticationError(
            message="Invalid or expired token",
            code=ErrorCodes.UNAUTHORIZED.code
        )
    
    return user_info


async def get_current_user_id(user_info: Dict[str, Any] = Depends(get_current_user)) -> str:
    """获取当前用户 ID 的便捷依赖函数
    
    Args:
        user_info: 当前用户信息
        
    Returns:
        用户 ID 字符串
        
    Raises:
        AuthenticationError: 当用户 ID 不存在时，返回统一的错误响应格式
    """
    user_id = user_info.get("sub")
    if not user_id:
        raise AuthenticationError(
            message="User ID not found in token",
            code=ErrorCodes.UNAUTHORIZED.code
        )
    return user_id


# 便捷的依赖别名
CurrentUserId = Depends(get_current_user_id) 