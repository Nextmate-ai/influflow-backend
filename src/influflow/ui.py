"""
Twitter Thread Generator UI
基于Streamlit的简单用户界面，用于生成Twitter thread
"""

import streamlit as st
import asyncio
from typing import Dict, Any
import uuid

# 导入graph
from influflow.graph import graph


def safe_asyncio_run(coro):
    """
    安全地在同步环境中运行异步协程，特别是在Streamlit中
    """
    try:
        try:
            # 尝试获取当前线程中正在运行的事件循环
            asyncio.get_running_loop()
            
            # 如果存在正在运行的循环，在一个新线程中运行协程以避免冲突
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()

        except RuntimeError:
            # 如果没有正在运行的循环，直接运行
            return asyncio.run(coro)
            
    except Exception as e:
        print(f"Error in async operation: {e}")
        return {"status": "error", "error": f"Async execution error: {str(e)}"}


async def generate_thread_async(topic: str, config: Dict[str, Any]):
    """异步生成Twitter thread"""
    try:
        # 准备输入数据
        input_data = {"topic": topic}
        
        # 流式获取结果
        final_result = None
        async for event in graph.astream(input_data, config):
            # 保存最后的结果
            if event:
                final_result = event
                
        # 返回最终结果
        if final_result and 'generate_tweet_thread' in final_result:
            return {
                "status": "success",
                "data": final_result['generate_tweet_thread']
            }
        else:
            return {"status": "error", "error": "No result generated"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_default_config(model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "configurable": {
            "writer_provider": "openai",
            "writer_model": model,
            "writer_model_kwargs": {}
        }
    }


def main():
    """主函数：构建Streamlit界面"""
    st.set_page_config(
        page_title="Twitter Thread Generator",
        page_icon="🐦",
        layout="wide"
    )
    
    st.title("🐦 Twitter Thread Generator")
    st.markdown("快速生成高质量的Twitter thread")
    st.markdown("---")
    
    # 初始化session state
    if 'generated_threads' not in st.session_state:
        st.session_state.generated_threads = []
    if 'current_result' not in st.session_state:
        st.session_state.current_result = None
    
    # 左侧边栏：模型配置
    with st.sidebar:
        st.header("⚙️ 配置")
        
        # 模型选择
        available_models = ["gpt-4.1","gpt-4.1-mini","gpt-4o-mini", "gpt-4o"]
        selected_model = st.selectbox(
            "选择模型:",
            available_models,
            index=0,
            help="选择用于生成Twitter thread的模型"
        )
        
        st.markdown("---")
        st.markdown("**当前配置:**")
        st.markdown(f"- 🤖 模型: {selected_model}")
        st.markdown("- 🔧 Provider: OpenAI")
    
    # 主界面
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 输入主题")
        
        # 主题输入框
        topic = st.text_area(
            "输入您想要创建Twitter thread的主题:",
            height=150,
            placeholder="例如：人工智能在医疗领域的最新突破",
            help="输入一个清晰的主题，系统将为您生成结构化的Twitter thread"
        )
        
        # 生成按钮
        if st.button("🚀 生成Thread", type="primary", use_container_width=True):
            if topic.strip():
                # 显示加载状态
                with st.spinner("正在生成Twitter thread..."):
                    # 获取配置
                    config = get_default_config(selected_model)
                    
                    # 调用异步函数生成thread
                    result = safe_asyncio_run(generate_thread_async(topic, config))
                    
                    if result["status"] == "success":
                        st.session_state.current_result = result["data"]
                        # 保存到历史记录
                        st.session_state.generated_threads.append({
                            "topic": topic,
                            "result": result["data"]
                        })
                        st.success("✅ Twitter thread生成成功！")
                        st.rerun()
                    else:
                        st.error(f"❌ 生成失败: {result.get('error', '未知错误')}")
            else:
                st.warning("请输入一个主题")
    
    with col2:
        st.subheader("📊 生成结果")
        
        if st.session_state.current_result:
            result = st.session_state.current_result
            
            # 使用tabs展示不同内容
            tab1, tab2 = st.tabs(["📋 大纲结构", "🐦 Twitter Thread"])
            
            with tab1:
                st.markdown("**文章大纲：**")
                # 显示outline_str
                if 'outline_str' in result:
                    with st.container(border=True):
                        st.text(result['outline_str'])
                else:
                    st.info("暂无大纲信息")
            
            with tab2:
                st.markdown("**Twitter Thread内容：**")
                # 直接使用outline对象显示结构化数据
                if 'outline' in result:
                    outline = result['outline']
                    
                    # 收集所有tweets以便计算总数
                    all_tweets = []
                    for node in outline.nodes:
                        for leaf_node in node.leaf_nodes:
                            all_tweets.append(leaf_node)
                    
                    total_tweets = len(all_tweets)
                    
                    # 遍历并显示每个tweet
                    tweet_index = 0
                    for node in outline.nodes:
                        for leaf_node in node.leaf_nodes:
                            tweet_index += 1
                            
                            # 为每条推文创建一个卡片样式的容器
                            with st.container(border=True):
                                # 显示tweet编号和内容
                                st.markdown(f"**({tweet_index}/{total_tweets})**")
                                
                                # 处理换行符，确保在Streamlit中正确显示，同时保持emoji等格式
                                formatted_content = leaf_node.tweet_content.replace('\n', '  \n')
                                st.markdown(formatted_content)
                                
                                # 显示字符数
                                char_count = len(leaf_node.tweet_content)
                                if char_count > 280:
                                    st.caption(f"⚠️ 字符数: {char_count}/280 (超出限制)")
                                else:
                                    st.caption(f"✅ 字符数: {char_count}/280")
                                
                                # 添加复制区域
                                st.markdown("**📋 复制到Twitter:**")
                                st.code(leaf_node.tweet_content, language="text")
                                st.caption("💡 点击代码框右上角的复制按钮，然后直接粘贴到Twitter")
                else:
                    st.info("暂无Twitter thread内容")
            
            # 下载按钮
            st.markdown("---")
            col_download1, col_download2 = st.columns(2)
            
            with col_download1:
                # 下载大纲
                if 'outline_str' in result:
                    st.download_button(
                        label="📥 下载大纲",
                        data=result['outline_str'],
                        file_name="thread_outline.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            with col_download2:
                # 下载Twitter thread
                if 'outline' in result:
                    # 动态生成thread内容用于下载
                    outline = result['outline']
                    all_tweets = []
                    for node in outline.nodes:
                        for leaf_node in node.leaf_nodes:
                            all_tweets.append(leaf_node)
                    
                    total_tweets = len(all_tweets)
                    thread_content = []
                    for i, leaf_node in enumerate(all_tweets, 1):
                        thread_content.append(f"({i}/{total_tweets}) {leaf_node.tweet_content}")
                    
                    download_content = "\n\n".join(thread_content)
                    
                    st.download_button(
                        label="📥 下载Thread",
                        data=download_content,
                        file_name="twitter_thread.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
        else:
            st.info("👈 请在左侧输入主题并点击生成按钮")
    
    # 历史记录（可选）
    if st.session_state.generated_threads:
        st.markdown("---")
        st.subheader("📜 历史记录")
        
        # 显示最近的3个生成记录
        recent_threads = st.session_state.generated_threads[-3:]
        cols = st.columns(3)
        
        for i, thread_data in enumerate(reversed(recent_threads)):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**主题：** {thread_data['topic'][:50]}...")
                    if st.button("查看", key=f"view_{len(st.session_state.generated_threads)-i-1}"):
                        st.session_state.current_result = thread_data['result']
                        st.rerun()
    
    # 页脚
    st.markdown("---")
    st.caption("💡 提示：输入清晰具体的主题可以获得更好的生成效果")


if __name__ == "__main__":
    main() 