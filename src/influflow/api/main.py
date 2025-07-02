"""
FastAPI应用主文件
提供Twitter AI功能的HTTP接口
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import traceback

from influflow.api.models import (
    GenerateThreadRequest, 
    ModifyTweetRequest, 
    ModifyOutlineRequest,
    GenerateThreadResponse,
    ModifyTweetResponse,
    ModifyOutlineResponse,
    HealthResponse,
    ErrorResponse,
    convert_internal_outline_to_api,
    convert_api_outline_to_internal,
    update_tweet_in_internal_outline
)
from influflow.services.twitter_service import twitter_service

# 创建FastAPI应用
app = FastAPI(
    title="InfluFlow AI Backend",
    description="提供Twitter Thread生成和编辑的AI功能",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root():
    """根路径，返回API基本信息"""
    return HealthResponse(
        status="running",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/twitter/generate", response_model=GenerateThreadResponse)
async def generate_twitter_thread(request: GenerateThreadRequest):
    """
    生成Twitter thread
    
    - **user_input**: 用户输入的原始文本，包含主题和可能的语言要求 (example: "Write a thread about AI in Chinese")
    """
    try:
        # 调用服务层原始方法（返回内部格式）
        result = twitter_service.generate_thread(
            user_input=request.user_input
        )
        
        if result["status"] == "success":
            # 在API层进行数据转换
            internal_outline = result["data"]["outline"]  # type: ignore
            api_outline = convert_internal_outline_to_api(internal_outline)
            
            return GenerateThreadResponse(
                status="success",
                outline=api_outline,
                error=None
            )
        else:
            return GenerateThreadResponse(
                status="error",
                outline=None,
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in generate_twitter_thread: {e}")
        print(traceback.format_exc())
        return GenerateThreadResponse(
            status="error",
            outline=None,
            error=f"Internal server error: {str(e)}"
        )


@app.post("/api/twitter/modify-tweet", response_model=ModifyTweetResponse)
async def modify_tweet(request: ModifyTweetRequest):
    """
    修改单个Tweet
    
    - **outline**: 完整的大纲结构
    - **tweet_number**: 要修改的Tweet编号
    - **modification_prompt**: 修改指令
    """
    try:
        # 在API层转换数据格式
        internal_outline = convert_api_outline_to_internal(request.outline)
        
        # 调用服务层原始方法（使用内部格式）
        result = twitter_service.modify_tweet(
            outline=internal_outline,
            tweet_number=request.tweet_number,
            modification_prompt=request.modification_prompt
        )
        
        if result["status"] == "success":
            return ModifyTweetResponse(
                status="success",
                updated_tweet_content=result["data"]["updated_tweet"],  # type: ignore
                error=None
            )
        else:
            return ModifyTweetResponse(
                status="error",
                updated_tweet_content=None,
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in modify_tweet: {e}")
        print(traceback.format_exc())
        return ModifyTweetResponse(
            status="error",
            updated_tweet_content=None,
            error=f"Internal server error: {str(e)}"
        )


@app.post("/api/twitter/modify-outline", response_model=ModifyOutlineResponse)
async def modify_outline(request: ModifyOutlineRequest):
    """
    修改大纲结构
    
    - **original_outline**: 原始大纲结构
    - **new_outline_structure**: 新的大纲结构
    """
    try:
        # 在API层转换数据格式
        original_internal = convert_api_outline_to_internal(request.original_outline)
        new_internal_structure = convert_api_outline_to_internal(request.new_outline_structure)
        
        # 调用服务层原始方法（使用内部格式）
        result = twitter_service.modify_outline(
            original_outline=original_internal,
            new_outline_structure=new_internal_structure,
        )
        
        if result["status"] == "success":
            # 转换回API格式
            updated_internal_outline = result["data"]["outline"]  # type: ignore
            updated_api_outline = convert_internal_outline_to_api(updated_internal_outline)
            
            return ModifyOutlineResponse(
                status="success",
                updated_outline=updated_api_outline,
                error=None
            )
        else:
            return ModifyOutlineResponse(
                status="error",
                updated_outline=None,
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in modify_outline: {e}")
        print(traceback.format_exc())
        return ModifyOutlineResponse(
            status="error",
            updated_outline=None,
            error=f"Internal server error: {str(e)}"
        )


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    print(f"Global exception handler: {exc}")
    print(traceback.format_exc())
    return ErrorResponse(
        status="error",
        error="Internal server error",
        detail=str(exc)
    )


# 注意：uvicorn.run 不应该在这里调用，以避免在UI服务中意外启动API
# 如果需要直接运行此文件进行开发，请使用: uv run python -m influflow.api.main
# 或者使用专门的启动脚本: python start_api.py

if __name__ == "__main__":
    print("⚠️  请使用 'python start_api.py' 或 'uv run uvicorn influflow.api.main:app' 来启动API服务")
    print("❌ 直接运行此文件可能会与UI服务产生冲突") 