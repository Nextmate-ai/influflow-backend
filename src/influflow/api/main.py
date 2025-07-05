"""
FastAPI应用主文件
提供Twitter AI功能的HTTP接口
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import traceback
import json
import asyncio
from typing import Any
from sse_starlette import EventSourceResponse

from influflow.api.auth import CurrentUserId
from influflow.api.models import (
    GenerateThreadRequest, 
    ModifyTweetRequest, 
    ModifyOutlineRequest,
    GenerateImageRequest,
    GenerateThreadResponse,
    ModifyTweetResponse,
    ModifyOutlineResponse,
    GenerateImageResponse,
    HealthResponse,
    HealthData,
    ModifyTweetData,
    ModifyOutlineData,
    GenerateImageData,
    build_success_response,
    build_error_response,
    convert_internal_outline_to_api,
    convert_api_outline_to_internal,
    convert_api_personalization_to_internal,
    convert_internal_outline_to_db_model
)
from influflow.api.errcode import ErrorCodes
from influflow.services.twitter_service import twitter_service
from influflow.database.tweet_thread import insert_tweet_thread


def prepare_serializable_result(result: dict) -> Any:
    """
    准备可序列化的结果，处理Outline对象等复杂类型，并过滤掉无用的字段
    """
    import copy
    
    # 深拷贝避免修改原始数据
    serializable_result = copy.deepcopy(result)
    
    def convert_outline_to_dict(obj):
        """递归转换Outline对象为字典"""
        if isinstance(obj, dict):
            converted = {}
            for key, value in obj.items():
                if key == "final_outline" and hasattr(value, "model_dump"):
                    # 转换Outline对象为API格式
                    try:
                        converted[key] = convert_internal_outline_to_api(value).model_dump()
                    except Exception:
                        # 如果转换失败，使用基本信息
                        converted[key] = {
                            "topic": getattr(value, 'topic', ''),
                            "tweet_count": len([leaf for node in getattr(value, 'nodes', []) for leaf in getattr(node, 'leaf_nodes', [])])
                        }
                elif hasattr(value, "model_dump"):
                    # 其他Pydantic对象
                    converted[key] = value.model_dump()
                elif isinstance(value, (dict, list)):
                    converted[key] = convert_outline_to_dict(value)
                else:
                    converted[key] = value
            return converted
        elif isinstance(obj, list):
            return [convert_outline_to_dict(item) for item in obj]
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        else:
            return obj
    
    return convert_outline_to_dict(serializable_result)

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
    health_data = HealthData(
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )
    return build_success_response(data=health_data)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    health_data = HealthData(
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )
    return build_success_response(data=health_data)


@app.post("/api/twitter/generate", response_model=GenerateThreadResponse)
async def generate_twitter_thread(
    request: GenerateThreadRequest, 
    user_id: str = CurrentUserId
):
    """
    同步生成Twitter thread并储存到数据库
    
    - **user_input**: 用户输入的原始文本，包含主题和可能的语言要求 (example: "Write a thread about AI in Chinese")
    - **personalization**: 个性化设置（可选）
    
    需要JWT认证，会自动获取当前用户ID
    返回完整的生成结果
    """
    try:        
        # 转换personalization参数
        internal_personalization = convert_api_personalization_to_internal(request.personalization)
        
        # 调用服务层同步方法（返回内部格式）
        result = twitter_service.generate_thread(
            user_input=request.user_input,
            personalization=internal_personalization
        )
        
        if result["status"] == "success":
            # 在API层进行数据转换
            internal_outline = result["data"]["outline"]  # type: ignore
            api_outline = convert_internal_outline_to_api(internal_outline)

            # 储存到数据库
            try:
                # 将内部outline转换为数据库模型
                db_tweet_thread = convert_internal_outline_to_db_model(internal_outline, user_id)
                
                # 插入数据库
                thread_id = insert_tweet_thread(db_tweet_thread)
                api_outline.id = thread_id
                
            except Exception as db_error:
                # 数据库错误不应影响主要功能，记录错误但继续返回结果
                print(f"Warning: Failed to save to database: {db_error}")
            
            return build_success_response(
                data=api_outline
            )
        else:
            # 使用业务错误码返回内部错误
            return build_error_response(
                message=result.get('error', 'Failed to generate twitter thread')
            )
            
    except Exception as e:
        print(f"Error in generate_twitter_thread: {e}")
        print(traceback.format_exc())
        # 使用业务错误码返回内部错误
        return build_error_response(
            message=f"AI generation error: {str(e)}",
            code=ErrorCodes.INTERNAL_ERROR.code
        )


@app.post("/api/twitter/generate/stream")
async def generate_twitter_thread_stream(
    request: GenerateThreadRequest,
    http_request: Request
):
    """
    SSE流式生成Twitter thread
    
    - **user_input**: 用户输入的原始文本，包含主题和可能的语言要求
    - **personalization**: 个性化设置（可选）
    
    返回Server-Sent Events (SSE)格式的流式数据
    需要JWT认证，会自动获取当前用户ID
    支持实时进度更新和推文生成过程
    """
    async def stream_generator():
        try:
            # 转换personalization参数
            internal_personalization = convert_api_personalization_to_internal(request.personalization)
            
            # 调用服务层的流式方法
            async for result in twitter_service.generate_thread_enhanced_stream_async(
                user_input=request.user_input,
                config=twitter_service.get_default_config(),
                personalization=internal_personalization
            ):
                # 检查客户端是否断开连接
                if await http_request.is_disconnected():
                    break
                
                # 过滤事件，只保留必要的业务事件
                event_type = result.get("status", "update")
                
                # 跳过LangGraph的内部节点更新事件
                if event_type == "node_update":
                    continue
                
                # 根据事件类型设置不同的事件名
                if event_type == "progress":
                    event_name = "progress"
                elif event_type == "error":
                    event_name = "error"
                else:
                    event_name = "update"
                
                # 处理包含Outline对象的数据序列化
                try:
                    serializable_result = prepare_serializable_result(result)
                    data_str = json.dumps(serializable_result, ensure_ascii=False)
                    event_id = str(hash(str(serializable_result)))
                except Exception as serialize_error:
                    # 序列化失败时，发送简化的错误信息
                    serializable_result = {
                        "status": result.get("status", "error"),
                        "error": f"Serialization error: {str(serialize_error)}",
                        "original_data_keys": list(result.keys()) if isinstance(result, dict) else str(type(result))
                    }
                    data_str = json.dumps(serializable_result, ensure_ascii=False)
                    event_id = str(hash(data_str))
                
                # 生成SSE事件
                yield {
                    "event": event_name,
                    "data": data_str,
                    "id": event_id
                }
                
        except asyncio.CancelledError:
            # 客户端断开连接时的清理
            print(f"SSE connection cancelled")
            raise
        except Exception as e:
            # 发送错误事件
            yield {
                "event": "error",
                "data": json.dumps({
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stage": "api_layer"
                }, ensure_ascii=False)
            }
    
    return EventSourceResponse(
        stream_generator(),
        ping=15,  # 每15秒发送ping保持连接
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
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
            modify_data = ModifyTweetData(
                updated_tweet_content=result["data"]["updated_tweet"]  # type: ignore
            )
            return build_success_response(data=modify_data)
        else:
            # 使用业务错误码返回内部错误
            return build_error_response(
                message=result.get('error', 'Failed to modify tweet'),
                code=ErrorCodes.INTERNAL_ERROR.code
            )
            
    except Exception as e:
        print(f"Error in modify_tweet: {e}")
        print(traceback.format_exc())
        # 使用业务错误码返回内部错误
        return build_error_response(
            message=f"Tweet modification error: {str(e)}",
            code=ErrorCodes.INTERNAL_ERROR.code
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
            
            modify_data = ModifyOutlineData(
                updated_outline=updated_api_outline
            )
            return build_success_response(data=modify_data)
        else:
            # 使用业务错误码返回内部错误
            return build_error_response(
                message=result.get('error', 'Failed to modify outline'),
                code=ErrorCodes.INTERNAL_ERROR.code
            )
            
    except Exception as e:
        print(f"Error in modify_outline: {e}")
        print(traceback.format_exc())
        # 使用业务错误码返回内部错误
        return build_error_response(
            message=f"Outline modification error: {str(e)}",
            code=ErrorCodes.INTERNAL_ERROR.code
        )


@app.post("/api/twitter/generate-image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest):
    """
    为推文生成配图
    
    - **target_tweet**: 目标推文内容
    - **tweet_thread**: 完整的推文串上下文
    
    返回生成的图片URL
    """
    try:
        # 调用服务层方法生成图片
        result = twitter_service.generate_image(
            target_tweet=request.target_tweet,
            tweet_thread=request.tweet_thread
        )
        
        if result["status"] == "success":
            image_data = GenerateImageData(
                image_url=result["data"]["image_url"]  # type: ignore
            )
            return build_success_response(data=image_data)
        else:
            # 使用业务错误码返回内部错误
            return build_error_response(
                message=result.get('error', 'Failed to generate image'),
                code=ErrorCodes.INTERNAL_ERROR.code
            )
            
    except Exception as e:
        print(f"Error in generate_image: {e}")
        print(traceback.format_exc())
        # 使用业务错误码返回内部错误
        return build_error_response(
            message=f"Image generation error: {str(e)}",
            code=ErrorCodes.INTERNAL_ERROR.code
        )


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    print(f"Global exception handler: {exc}")
    print(traceback.format_exc())
    # 使用业务错误码返回内部错误
    return build_error_response(
        message=f"Unexpected error: {str(exc)}",
        code=ErrorCodes.INTERNAL_ERROR.code
    )


# 注意：uvicorn.run 不应该在这里调用，以避免在UI服务中意外启动API
# 如果需要直接运行此文件进行开发，请使用: uv run python -m influflow.api.main
# 或者使用专门的启动脚本: python start_api.py

if __name__ == "__main__":
    print("⚠️  请使用 'python start_api.py' 或 'uv run uvicorn influflow.api.main:app' 来启动API服务")
    print("❌ 直接运行此文件可能会与UI服务产生冲突") 