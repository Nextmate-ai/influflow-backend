"""Supabase Storage Module.

处理Supabase Storage相关的操作，包括：
- 图片上传
- 文件管理
- URL获取
"""

import base64
import uuid

from .singleton import get_supabase_client


def upload_image_to_supabase(image_b64: str) -> str:
    """将base64图片数据上传到Supabase Storage并返回公共URL.
    
    Args:
        image_b64: base64编码的图片数据
        
    Returns:
        图片的公共URL
        
    Raises:
        ValueError: 当环境变量缺失或上传失败时
        ImportError: 当Supabase SDK未安装时
    """
    try:
        # 获取Supabase客户端（单例）
        supabase = get_supabase_client()
        
        # 解码base64数据为字节
        image_bytes = base64.b64decode(image_b64)
        
        # 生成唯一的文件名
        file_name = f"{uuid.uuid4().hex}.png"
        
        # 使用固定的存储桶名称
        bucket_name = "images"
        
        # 上传文件到Supabase Storage
        response = supabase.storage.from_(bucket_name).upload(  # type: ignore
            path=file_name,
            file=image_bytes,
            file_options={"content-type": "image/png"}  # type: ignore
        )
        
        # 检查上传是否成功
        if hasattr(response, 'status_code') and response.status_code not in [200, 201]:  # type: ignore
            raise ValueError(f"Upload failed with status code: {response.status_code}")  # type: ignore
        
        # 获取公共URL
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_name)  # type: ignore
        
        if not public_url_response:
            raise ValueError("Failed to get public URL for uploaded image")
            
        return public_url_response
        
    except ImportError:
        raise
    except Exception as e:
        # 如果上传失败，返回详细错误信息
        raise ValueError(f"Failed to upload image to Supabase: {str(e)}")