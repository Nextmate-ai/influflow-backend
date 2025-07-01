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
    
    - **topic**: Twitter thread的主题内容 (example: "What is BTC?")
    """
    try:
        # 调用服务层原始方法（返回内部格式）
        result = twitter_service.generate_thread(
            topic=request.topic
        )
        
        if result["status"] == "success":
            # 在API层进行数据转换
            internal_outline = result["data"]["outline"]
            api_outline = convert_internal_outline_to_api(internal_outline)
            
            return GenerateThreadResponse(
                status="success",
                outline=api_outline
            )
        else:
            return GenerateThreadResponse(
                status="error",
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in generate_twitter_thread: {e}")
        print(traceback.format_exc())
        return GenerateThreadResponse(
            status="error",
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
                updated_tweet_content=result["data"]["updated_tweet"]
            )
        else:
            return ModifyTweetResponse(
                status="error",
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in modify_tweet: {e}")
        print(traceback.format_exc())
        return ModifyTweetResponse(
            status="error",
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
            updated_internal_outline = result["data"]["outline"]
            updated_api_outline = convert_internal_outline_to_api(updated_internal_outline)
            
            return ModifyOutlineResponse(
                status="success",
                updated_outline=updated_api_outline
            )
        else:
            return ModifyOutlineResponse(
                status="error",
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        print(f"Error in modify_outline: {e}")
        print(traceback.format_exc())
        return ModifyOutlineResponse(
            status="error",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 