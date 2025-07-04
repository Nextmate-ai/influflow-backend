from typing import List
from ..models.tweet_thread import TweetThread
from .singleton import get_supabase_client


def insert_tweet_thread(tweet_thread: TweetThread) -> str:
    """
    将一个 TweetThread 对象插入到 Supabase 数据库的 'tweet_thread' 表中。

    该函数会将 Pydantic 模型对象转换为与数据库表结构匹配的字典，
    特别是处理 JSONB 类型的 'tweets' 字段，并将 'sections' 字段的数据存入其中。

    Args:
        tweet_thread: 要插入数据库的 TweetThread 对象。

    Returns:
        插入成功后的记录 ID。

    Raises:
        ValueError: 如果插入操作失败，会抛出此异常。
    """
    supabase = get_supabase_client()
    
    # 将 sections 列表转换为 JSON 兼容的字典列表
    sections_as_dict = [section.model_dump() for section in tweet_thread.tweets]
    
    data_to_insert = {
        "id": str(tweet_thread.id),
        "uid": tweet_thread.uid,
        "topic": tweet_thread.topic,
        "tweets": sections_as_dict,  # 将 'sections' 映射到 'tweets' 字段
        "created_at": tweet_thread.created_at.isoformat(),
        "updated_at": tweet_thread.updated_at.isoformat(),  # 将 'updated_at' 映射到 'update_at' 字段
    }

    try:
        response = supabase.table("tweet_thread").insert(data_to_insert).execute()
        return response.data[0]["id"]
    except Exception as e:
        # 捕获其他可能的异常，例如网络问题或API错误
        raise ValueError(f"An error occurred while inserting tweet thread: {str(e)}") 


def get_tweet_thread_by_id(thread_id: str) -> TweetThread:
    """
    根据 thread_id 从 Supabase 数据库获取一条 tweet_thread 记录。
    Args:
        thread_id: tweet_thread 的唯一标识符。
    Returns:
        TweetThread 对象。
    Raises:
        ValueError: 如果未找到记录或查询失败。
    """
    supabase = get_supabase_client()
    try:
        response = supabase.table("tweet_thread").select("*").eq("id", thread_id).single().execute()
        data = response.data
        if not data:
            raise ValueError(f"No tweet_thread found with id: {thread_id}")
        return TweetThread.model_validate(data)
    except Exception as e:
        raise ValueError(f"An error occurred while fetching tweet thread: {str(e)}")


def get_tweet_threads_by_user_id(user_id: str) -> List[TweetThread]:
    """
    根据 user_id 获取该用户的所有 tweet_thread 记录。
    Args:
        user_id: 用户唯一标识符。
    Returns:
        TweetThread 对象列表。
    Raises:
        ValueError: 查询失败时抛出。
    """
    supabase = get_supabase_client()
    try:
        response = supabase.table("tweet_thread").select("*").eq("uid", user_id).execute()
        data_list = response.data or []
        tweet_threads = []
        for data in data_list:
            tweet_threads.append(TweetThread.model_validate(data))
        return tweet_threads
    except Exception as e:
        raise ValueError(f"An error occurred while fetching tweet threads: {str(e)}") 