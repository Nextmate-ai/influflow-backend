"""
Twitter Thread Generator UI
基于Streamlit的简单用户界面，使用服务层架构
"""

import streamlit as st
import time
import os

# 尝试导入服务层，如果失败则显示错误信息
try:
    from influflow.services.twitter_service import twitter_service
    from influflow.ai.state import Outline, OutlineNode, OutlineLeafNode, Personalization, ToneStyle
    SERVICES_AVAILABLE = True
except ImportError as e:
    SERVICES_AVAILABLE = False
    IMPORT_ERROR = str(e)
except Exception as e:
    SERVICES_AVAILABLE = False
    IMPORT_ERROR = f"服务初始化失败: {str(e)}"

def show_error_page():
    """显示错误页面，提示用户配置环境变量"""
    st.set_page_config(
        page_title="配置错误 - Twitter Thread Generator",
        page_icon="⚠️",
        layout="wide"
    )
    
    st.title("⚠️ 配置错误")
    st.error("无法启动AI服务，可能缺少必要的环境变量配置")
    
    st.markdown("### 🔧 解决方法")
    st.markdown("""
    请确保已设置以下环境变量：
    
    **OPENAI_API_KEY** - OpenAI API密钥
    
    #### Railway部署：
    1. 前往Railway项目dashboard
    2. 点击 Settings -> Environment Variables
    3. 添加环境变量：
       - `OPENAI_API_KEY` = `your_openai_api_key_here`
    4. 重新部署应用
    
    #### 本地开发：
    1. 在项目根目录创建 `.env` 文件
    2. 添加以下内容：
       ```
       OPENAI_API_KEY=your_openai_api_key_here
       ```
    3. 重启应用
    """)
    
    st.markdown("### 🔍 错误详情")
    if 'IMPORT_ERROR' in globals():
        st.code(IMPORT_ERROR, language="text")
    
    # 检查当前环境变量状态
    st.markdown("### 📊 环境变量状态")
    if os.environ.get('OPENAI_API_KEY'):
        st.success("✅ OPENAI_API_KEY: 已设置")
    else:
        st.error("❌ OPENAI_API_KEY: 未设置")


def typewriter_stream(text: str):
    """模拟打字机效果的生成器"""
    for char in text:
        yield char
        time.sleep(0.005)


def count_twitter_chars(text: str) -> int:
    """
    统计Twitter字符数，中文字符计为2个字符，英文字符计为1个字符，Unicode粗体字符计为2个字符
    """
    char_count = 0
    for char in text:
        # 判断是否为中文字符（包括中文标点符号）
        if '\u4e00' <= char <= '\u9fff' or '\u3000' <= char <= '\u303f' or '\uff00' <= char <= '\uffef':
            char_count += 2  # 中文字符计为2个字符
        # 判断是否为Unicode粗体字符 (Mathematical Alphanumeric Symbols)
        elif '\U0001d400' <= char <= '\U0001d7ff':
            char_count += 2  # Unicode粗体字符计为2个字符
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
        
        st.header("✨ 个性化")
        st.markdown("填写以下信息，让内容更具个人风格。")

        account_name = st.text_input(
            "推特用户名 (可选)",
            placeholder="@elonmusk",
            help="输入您的推特用户名，例如 @elonmusk"
        )
        
        identity = st.text_input(
            "身份定位 (可选)",
            placeholder="AI Founder, Web3 Builder...",
            help="一句话描述您的身份，例如 'AI创始人', 'Web3建设者'"
        )

        style_options = [""] + [style.value for style in ToneStyle]
        selected_style_value = st.selectbox(
            "语调风格 (可选):",
            options=style_options,
            index=0,
            format_func=lambda x: {
                "": "不选择特定风格",
                "Conversational": "对话式 - 友好易懂，轻量表情符号",
                "Humorous": "幽默式 - 巧妙双关，网络梗文化",
                "Analytical": "分析式 - 数据驱动，事实解读",
                "Motivational": "激励式 - 充满活力，成功故事",
                "Expert": "专家式 - 精确术语，正式引用"
            }.get(x, x),
            help="选择您偏好的语调风格，每种风格都有独特的表达方式和情感色彩"
        )
        
        bio = st.text_area(
            "个人简介 (可选):",
            height=100,
            placeholder="您的个人简介，包括背景、专业领域、价值观等 (建议200字以内)",
            help="输入您的个人简介，这将帮助AI更好地模仿您的语气和风格"
        )
        
        st.markdown("---")
        st.markdown("**当前配置:**")
        st.markdown(f"- 🤖 模型: {selected_model}")
        st.markdown(f"- 🌍 语言: {selected_language}")
        st.markdown("- 🔧 Provider: OpenAI")
        st.markdown("- ⚡ 架构: 服务层")
    
    # 主界面
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 输入内容")
        
        # 内容输入框
        topic = st.text_area(
            "输入您想要创建Twitter thread的内容:",
            height=150,
            placeholder="例如：我想写一个关于人工智能在医疗领域最新突破的推文串，用中文写\n或者：Can you create a thread about sustainable energy solutions?\n或者：最近看到一个很有趣的创业故事，想分享给大家",
            help="您可以用自然语言描述想要的Twitter thread内容，包括主题、语言要求、风格等。系统会自动分析并生成结构化的推文串。"
        )
        
        # 生成按钮
        if st.button("🚀 生成Thread", type="primary", use_container_width=True):
            if topic.strip():
                # 创建Personalization对象
                personalization = Personalization(
                    account_name=account_name if account_name else None,
                    identity=identity if identity else None,
                    tone=ToneStyle(selected_style_value) if selected_style_value else None,
                    bio=bio if bio else None
                )

                # 显示加载状态
                with st.spinner("正在分析输入并生成Twitter thread..."):
                    # 调用服务层 - 现在使用同步接口，传递原始用户输入和个性化信息
                    result = twitter_service.generate_thread(
                        user_input=topic,  # topic现在是原始用户输入
                        model=selected_model,
                        personalization=personalization
                    )
                    
                    if result["status"] == "success":
                        result_data = result["data"]
                        # 如果没有outline_str，则生成它
                        if isinstance(result_data, dict) and 'outline' in result_data and 'outline_str' not in result_data:
                            outline_obj = result_data.get('outline')
                            if outline_obj is not None:
                                try:
                                    result_data['outline_str'] = outline_obj.display_outline()
                                except AttributeError:
                                    # 如果没有display_outline方法，跳过
                                    pass
                        
                        st.session_state.current_result = result_data
                        # 保存到历史记录，包含language和personalization信息
                        st.session_state.generated_threads.append({
                            "input_text": topic,  # 改为input_text，更准确描述
                            "language": selected_language,
                            "personalization": personalization,
                            "result": result_data
                        })
                        st.session_state.display_mode = 'initial'  # 标记为初始生成
                        st.success("✅ Twitter thread生成成功！")
                        st.rerun()
                    else:
                        st.error(f"❌ 生成失败: {result.get('error', '未知错误')}")
            else:
                st.warning("请输入内容")
    
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
                            # 检查编辑后的大纲是否为空
                            if not edited_outline_str or edited_outline_str.strip() == "":
                                st.error("大纲内容不能为空，请输入有效的大纲内容")
                                st.stop()
                            
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
                                    # 处理返回的数据结构 - 现在outline在'outline'字段中
                                    if isinstance(updated_data, dict):
                                        # 获取更新后的outline
                                        updated_outline = updated_data.get('outline')
                                        if updated_outline is not None:
                                            st.session_state.current_result['outline'] = updated_outline
                                            # 生成outline_str
                                            try:
                                                st.session_state.current_result['outline_str'] = updated_outline.display_outline()
                                            except AttributeError:
                                                pass
                                    
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
                                                        # 手动更新本地的outline对象
                                                        if isinstance(updated_data, dict) and 'updated_tweet' in updated_data:
                                                            new_tweet_content = updated_data['updated_tweet']
                                                            # 找到并更新指定的tweet（使用当前正在修改的tweet编号）
                                                            current_outline = st.session_state.current_result['outline']
                                                            target_tweet_number = leaf_node.tweet_number  # 从外层循环获取
                                                            for node in current_outline.nodes:
                                                                for leaf in node.leaf_nodes:
                                                                    if leaf.tweet_number == target_tweet_number:
                                                                        leaf.tweet_content = new_tweet_content
                                                                        break
                                                            # 重新生成outline_str
                                                            try:
                                                                st.session_state.current_result['outline_str'] = current_outline.display_outline()
                                                            except AttributeError:
                                                                pass
                                                        
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
            st.info("👈 请在左侧输入内容并点击生成按钮")
    
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
                    # 兼容处理：支持旧的'topic'字段和新的'input_text'字段
                    display_text = thread_data.get('input_text') or thread_data.get('topic', 'Unknown')
                    st.markdown(f"**输入：** {display_text[:50]}...")
                    # 显示语言信息（如果存在）
                    if 'language' in thread_data:
                        st.markdown(f"**语言：** {thread_data['language']}")
                    # 显示个性化信息（如果存在）
                    if 'personalization' in thread_data and thread_data['personalization']:
                        personalization = thread_data['personalization']
                        if personalization.account_name:
                            st.markdown(f"**用户：** {personalization.account_name}")
                        if personalization.identity:
                            st.markdown(f"**身份：** {personalization.identity}")
                        if personalization.tone:
                            st.markdown(f"**语调：** {personalization.tone}")
                    if st.button("查看", key=f"view_{len(st.session_state.generated_threads)-i-1}"):
                        st.session_state.current_result = thread_data['result']
                        st.rerun()
    
    # 页脚
    st.markdown("---")
    st.caption("💡 提示：用自然语言描述您想要的Twitter thread内容，可以包含主题、语言、风格等要求")
    st.caption("⚡ 当前使用服务层架构，同时支持API和UI访问")


if __name__ == "__main__":
    if SERVICES_AVAILABLE:
        main()
    else:
        show_error_page() 