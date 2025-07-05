import uuid
import random
import string
import os
from datetime import datetime

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有 python-dotenv，直接使用环境变量
    pass

from influflow.models.tweet_thread import TweetThread, TweetSection, Tweet
from influflow.database.tweet_thread import insert_tweet_thread, get_tweet_thread_by_id, get_tweet_threads_by_user_id
from influflow.database.singleton import get_supabase_client


def random_str(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def get_test_user_id():
    """获取一个测试用的真实用户ID"""
    try:
        supabase = get_supabase_client()
        # 尝试从 auth.users 获取一个用户ID
        response = supabase.rpc('get_user_id').execute()  # 如果有这个函数
        if response.data:
            return response.data
    except:
        pass
    
    # 如果上面的方法不行，你需要手动提供一个真实的用户ID
    # 或者在这里返回你知道存在的用户ID
    return "2587bf97-9d5d-416e-98dc-d08fedeaa776"  # 真实的用户ID


def test_insert_and_get_tweet_thread():
    # 获取测试用的真实用户ID
    test_uid = get_test_user_id()
    
    if test_uid == "请在这里填入真实的用户ID":
        print("⚠️  警告：请在 get_test_user_id() 函数中提供真实的用户ID")
        return
    
    test_topic = f"TestTopic_{random_str()}"
    now = datetime.utcnow()
    tweet = Tweet(title="Test Tweet", tweet_number=1, content="Hello World!", image_url="https://www.google.com")
    section = TweetSection(title="Section 1", tweets=[tweet])
    thread = TweetThread(
        id=uuid.uuid4(),
        uid=test_uid,
        topic=test_topic,
        tweets=[section],
        created_at=now,
        updated_at=now
    )

    # 插入数据库
    insert_result = insert_tweet_thread(thread)
    assert insert_result, "Insert result should not be empty"

    # 通过 id 读取
    fetched = get_tweet_thread_by_id(str(thread.id))
    assert fetched.id == thread.id
    assert fetched.uid == thread.uid
    assert fetched.topic == thread.topic
    assert fetched.tweets[0].title == section.title
    assert fetched.tweets[0].tweets[0].content == tweet.content

    # 通过 uid 读取
    fetched_list = get_tweet_threads_by_user_id(test_uid)
    assert any(t.id == thread.id for t in fetched_list)

    # 展示结果
    print(f"插入的推文串: {thread.topic}")
    print(f"插入的推文串: {thread.tweets[0].title}")
    print(f"插入的推文串: {thread.tweets[0].tweets[0].content}")
    print(f"插入的推文串: {thread.tweets[0].tweets[0].image_url}")
    print(f"插入的推文串: {thread.tweets[0].tweets[0].tweet_number}")
    print(f"插入的推文串: {thread.tweets[0].tweets[0].title}")


if __name__ == "__main__":
    try:
        print("开始测试 TweetThread 数据库读写...")
        test_insert_and_get_tweet_thread()
        print("✅ 测试通过！数据库读写功能正常")
    except Exception as e:
        print(f"❌ 测试失败：{str(e)}")
        raise 