"""
Twitter Thread Generator UI
基于Streamlit的简单用户界面，使用服务层架构
"""

import streamlit as st
import time

# 导入服务层
from influflow.services.twitter_service import twitter_service
from influflow.ai.state import Outline, OutlineNode, OutlineLeafNode


def typewriter_stream(text: str):
    """模拟打字机效果的生成器"""
    for char in text:
        yield char
        time.sleep(0.005)


def count_twitter_chars(text: str) -> int:
    """
    统计Twitter字符数，中文字符计为2个字符，英文字符计为1个字符
    """
    char_count = 0
    for char in text:
        # 判断是否为中文字符（包括中文标点符号）
        if '\u4e00' <= char <= '\u9fff' or '\u3000' <= char <= '\u303f' or '\uff00' <= char <= '\uffef':
            char_count += 2  # 中文字符计为2个字符
        else:
            char_count += 1  # 英文字符计为1个字符
    return char_count


def main():
    """主函数：构建Streamlit界面"""
    st.set_page_config(
        page_title="Twitter Thread Generator",
        page_icon="🐦",
        layout="wide"
    )
    
    st.title("🐦 Twitter Thread Generator")
    st.markdown("快速生成高质量的Twitter thread - 现在使用服务层架构")
    st.markdown("---")
    
    # 初始化session state
    if 'generated_threads' not in st.session_state:
        st.session_state.generated_threads = []
    if 'current_result' not in st.session_state:
        st.session_state.current_result = None
    if 'editing_tweet_number' not in st.session_state:
        st.session_state.editing_tweet_number = None
    if 'display_mode' not in st.session_state:
        st.session_state.display_mode = None
    if 'last_modified_tweet_number' not in st.session_state:
        st.session_state.last_modified_tweet_number = None
    
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
        
        # 语言选择
        available_languages = [
            ("英文", "English"),
            ("中文", "Chinese")
        ]
        
        language_options = [f"{name} ({code})" for name, code in available_languages]
        selected_language_display = st.selectbox(
            "选择生成语言:",
            language_options,
            index=0,  # 默认选择中文
            help="选择生成Twitter thread的语言"
        )
        
        # 从显示文本中提取语言代码
        selected_language = available_languages[language_options.index(selected_language_display)][1]
        
        st.markdown("---")
        st.markdown("**当前配置:**")
        st.markdown(f"- 🤖 模型: {selected_model}")
        st.markdown(f"- 🌍 语言: {selected_language}")
        st.markdown("- 🔧 Provider: OpenAI")
        st.markdown("- ⚡ 架构: 服务层")
    
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
                with st.spinner(f"正在用{selected_language}生成Twitter thread..."):
                    # 调用服务层 - 现在使用同步接口
                    result = twitter_service.generate_thread(
                        topic=topic,
                        language=selected_language,
                        model=selected_model
                    )
                    
                    if result["status"] == "success":
                        st.session_state.current_result = result["data"]
                        # 保存到历史记录，包含language信息
                        st.session_state.generated_threads.append({
                            "topic": topic,
                            "language": selected_language,
                            "result": result["data"]
                        })
                        st.session_state.display_mode = 'initial'  # 标记为初始生成
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
                if 'outline_str' in result and 'outline' in result:
                    with st.container(border=True):
                        # 大纲现在是可编辑的
                        outline_edit_key = f"outline_edit_{len(st.session_state.generated_threads)}"
                        
                        edited_outline_str = st.text_area(
                            "可编辑大纲 (bullet point格式):",
                            value=result['outline_str'],
                            height=300,
                            key=outline_edit_key,
                            help="您可以直接在这里修改大纲结构，然后点击下方按钮更新。系统会保留未修改部分的推文内容。"
                        )

                        if st.button("🔄 更新大纲", use_container_width=True, type="primary"):
                            original_outline: Outline = result['outline']
                            
                            # 1. 创建现有推文内容的映射
                            original_tweets_map = {
                                leaf.title: leaf.tweet_content for node in original_outline.nodes for leaf in node.leaf_nodes
                            }

                            # 2. 解析编辑后的大纲文本
                            # 修正解析逻辑以匹配实际的display_outline格式
                            lines = edited_outline_str.strip().split('\n')
                            new_topic = original_outline.topic
                            parsed_nodes = []
                            current_node_leaves = None

                            for line in lines:
                                stripped_line = line.strip()
                                if not stripped_line:
                                    continue
                                
                                # 修正：匹配"Topic:"而不是"主题:"
                                if stripped_line.startswith("Topic:"):
                                    new_topic = stripped_line[len("Topic:"):].strip()
                                    continue

                                # 修正解析逻辑，匹配实际的格式
                                # 叶子节点：以"   - "开始（三个空格加短横线）
                                is_leaf = line.startswith("   -")
                                # 主节点：以"- "开始且不是叶子节点
                                is_node = line.startswith("- ") and not is_leaf

                                if is_node:
                                    title = stripped_line.lstrip('- ').strip()
                                    current_node_leaves = []
                                    parsed_nodes.append({"title": title, "leaf_nodes": current_node_leaves})
                                elif is_leaf:
                                    # 只有在当前有主节点的情况下才添加叶子节点
                                    if current_node_leaves is not None:
                                        title = stripped_line.lstrip('- ').strip()
                                        current_node_leaves.append({"title": title})

                            # 3. 构建新的Outline结构，但暂时不填充内容
                            new_nodes = []
                            tweet_counter = 1  # 从1开始计算tweet编号
                            for node_data in parsed_nodes:
                                new_leaf_nodes = []
                                for leaf_data in node_data['leaf_nodes']:
                                    new_leaf_nodes.append(OutlineLeafNode(
                                        title=leaf_data['title'],
                                        tweet_number=tweet_counter,  # 使用计算出的tweet编号
                                        tweet_content="",  # 先置为空
                                    ))
                                    tweet_counter += 1  # 递增计数器
                                new_nodes.append(OutlineNode(title=node_data['title'], leaf_nodes=new_leaf_nodes))
                            
                            new_outline_structure = Outline(topic=new_topic, nodes=new_nodes)

                            # 4. 根据标题从原始映射中填充内容
                            for node in new_outline_structure.nodes:
                                for leaf in node.leaf_nodes:
                                    leaf.tweet_content = original_tweets_map.get(leaf.title, "")

                            # 5. 调用服务层进行更新
                            with st.spinner("正在更新大纲并重新生成内容..."):
                                mod_result = twitter_service.modify_outline(
                                    original_outline=original_outline,
                                    new_outline_structure=new_outline_structure,
                                    model=selected_model
                                )
                                
                                # 6. 处理结果
                                if mod_result["status"] == "success":
                                    updated_data = mod_result["data"]
                                    st.session_state.current_result['outline'] = updated_data['updated_outline']
                                    st.session_state.current_result['outline_str'] = updated_data['outline_str']
                                    
                                    # 更新历史记录
                                    if st.session_state.generated_threads:
                                        st.session_state.generated_threads[-1]['result'] = st.session_state.current_result
                                    
                                    st.session_state.display_mode = 'initial' # 标记为初始生成，但不再触发展示动画
                                    st.success("✅ 大纲更新成功！")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 大纲更新失败: {mod_result.get('error', '未知错误')}")
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
                    
                    # 获取显示模式
                    display_mode = st.session_state.get('display_mode')
                    last_modified_tweet = st.session_state.get('last_modified_tweet_number')
                    
                    # 遍历并显示每个tweet
                    for node in outline.nodes:
                        for leaf_node in node.leaf_nodes:
                            # 为每条推文创建一个卡片样式的容器
                            with st.container(border=True):
                                # 显示tweet编号和内容
                                st.markdown(f"**({leaf_node.tweet_number}/{total_tweets})**")
                                
                                # 根据模式决定是否使用打字机效果 (仅在修改单条时触发)
                                if display_mode == 'modification' and leaf_node.tweet_number == last_modified_tweet:
                                    st.write_stream(typewriter_stream(leaf_node.tweet_content))
                                else:
                                    # 静态显示
                                    formatted_content = leaf_node.tweet_content.replace('\n', '  \n')
                                    st.markdown(formatted_content)
                                
                                # 显示字符数（支持中文字符计数）
                                char_count = count_twitter_chars(leaf_node.tweet_content)
                                if char_count > 280:
                                    st.caption(f"⚠️ 字符数: {char_count}/280 (超出限制)")
                                else:
                                    st.caption(f"✅ 字符数: {char_count}/280")
                                
                                # --- 修改功能 ---
                                # 如果当前tweet正在被编辑，显示编辑界面
                                if st.session_state.editing_tweet_number == leaf_node.tweet_number:
                                    st.markdown("**✏️ 修改这条Tweet:**")
                                    modification_prompt = st.text_area(
                                        "输入修改指令:",
                                        key=f"mod_prompt_{leaf_node.tweet_number}",
                                        placeholder="例如：让语气更专业一些，或者增加一个相关的emoji"
                                    )
                                    
                                    col_mod1, col_mod2 = st.columns(2)
                                    with col_mod1:
                                        if st.button("✅ 提交修改", key=f"submit_mod_{leaf_node.tweet_number}", use_container_width=True, type="primary"):
                                            if modification_prompt.strip():
                                                with st.spinner("正在修改Tweet..."):
                                                    # 调用服务层
                                                    mod_result = twitter_service.modify_tweet(
                                                        outline=result['outline'], # 传递整个Outline对象
                                                        tweet_number=leaf_node.tweet_number,
                                                        modification_prompt=modification_prompt,
                                                        model=selected_model
                                                    )
                                                    
                                                    if mod_result["status"] == "success":
                                                        # 更新session state
                                                        updated_data = mod_result["data"]
                                                        st.session_state.current_result['outline'] = updated_data['updated_outline']
                                                        st.session_state.current_result['outline_str'] = updated_data['outline_str']
                                                        
                                                        # 更新历史记录中的当前结果
                                                        if st.session_state.generated_threads:
                                                            # 假设当前结果是历史记录的最后一个
                                                            st.session_state.generated_threads[-1]['result'] = st.session_state.current_result
                                                        
                                                        st.session_state.editing_tweet_number = None
                                                        st.session_state.display_mode = 'modification'
                                                        st.session_state.last_modified_tweet_number = leaf_node.tweet_number
                                                        st.success("✅ 修改成功！")
                                                        st.rerun()
                                                    else:
                                                        st.error(f"❌ 修改失败: {mod_result.get('error', '未知错误')}")
                                            else:
                                                st.warning("请输入修改指令")
                                    
                                    with col_mod2:
                                        if st.button("❌ 取消", key=f"cancel_mod_{leaf_node.tweet_number}", use_container_width=True):
                                            st.session_state.editing_tweet_number = None
                                            st.rerun()

                                # 否则，如果没有任何tweet在编辑，则显示修改按钮
                                elif st.session_state.editing_tweet_number is None:
                                    if st.button("✏️ 修改", key=f"modify_{leaf_node.tweet_number}", use_container_width=True):
                                        st.session_state.editing_tweet_number = leaf_node.tweet_number
                                        st.rerun()

                                # 添加复制区域
                                st.markdown("**📋 复制到Twitter:**")
                                st.code(leaf_node.tweet_content, language="text")
                                st.caption("💡 点击代码框右上角的复制按钮，然后直接粘贴到Twitter")
                
                    # 渲染完成后重置显示模式，以便下次rerun时静态显示
                    if display_mode:
                        st.session_state.display_mode = None
                    if last_modified_tweet:
                        st.session_state.last_modified_tweet_number = None
                        
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
                        thread_content.append(f"({leaf_node.tweet_number}/{total_tweets}) {leaf_node.tweet_content}")
                    
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
                    # 显示语言信息（如果存在）
                    if 'language' in thread_data:
                        st.markdown(f"**语言：** {thread_data['language']}")
                    if st.button("查看", key=f"view_{len(st.session_state.generated_threads)-i-1}"):
                        st.session_state.current_result = thread_data['result']
                        st.rerun()
    
    # 页脚
    st.markdown("---")
    st.caption("💡 提示：输入清晰具体的主题可以获得更好的生成效果")
    st.caption("⚡ 当前使用服务层架构，同时支持API和UI访问")


if __name__ == "__main__":
    main() 