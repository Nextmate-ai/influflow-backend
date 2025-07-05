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
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = {}  # 存储每个tweet的生成图片 {tweet_number: image_url}
    if 'generating_image_for_tweet' not in st.session_state:
        st.session_state.generating_image_for_tweet = None  # 正在生成图片的tweet编号
    if 'image_quality_settings' not in st.session_state:
        st.session_state.image_quality_settings = {}  # 存储每个tweet的图片质量设置 {tweet_number: quality}
    
    # 流式生成相关状态
    if 'streaming_generation' not in st.session_state:
        st.session_state.streaming_generation = False
    if 'streaming_data' not in st.session_state:
        st.session_state.streaming_data = []
    if 'streaming_complete' not in st.session_state:
        st.session_state.streaming_complete = False
    
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
        
        # 推文例子输入
        st.markdown("**📝 推文例子 (可选):**")
        st.markdown("提供您过往的推文或推文串作为写作风格参考，最多3个例子")
        
        tweet_examples = []
        for i in range(3):
            example = st.text_area(
                f"推文例子 {i+1}:",
                height=80,
                key=f"tweet_example_{i}",
                placeholder=f"粘贴您的第{i+1}个推文或推文串...",
                help="粘贴您过往发布的推文内容，AI将学习您的写作风格"
            )
            if example.strip():
                tweet_examples.append(example.strip())
        
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
        if st.button("⚡ 流式生成", type="primary", use_container_width=True):
            if topic.strip():
                # 创建Personalization对象
                personalization = Personalization(
                    account_name=account_name if account_name else None,
                    identity=identity if identity else None,
                    tone=ToneStyle(selected_style_value) if selected_style_value else None,
                    bio=bio if bio else None,
                    tweet_examples=tweet_examples if tweet_examples else None
                )
                
                # 启动流式生成
                st.session_state.streaming_generation = True
                st.session_state.streaming_topic = topic
                st.session_state.streaming_model = selected_model
                st.session_state.streaming_personalization = personalization
                st.session_state.streaming_language = selected_language
                st.rerun()
            else:
                st.warning("请输入内容")
    
    with col2:
        st.subheader("📊 生成结果")
        
        # 处理流式生成
        if st.session_state.streaming_generation:
            st.markdown("### ⚡ 流式生成中...")
            
            # 创建容器用于显示流式内容
            streaming_container = st.container()
            progress_container = st.container()
            
            with progress_container:
                st.info("🔄 正在连接AI模型...")
            
            # 使用真正的流式显示
            # 初始化流式状态
            if 'stream_tweets' not in st.session_state:
                st.session_state.stream_tweets = {}
            if 'stream_topic' not in st.session_state:
                st.session_state.stream_topic = ""
            if 'stream_analysis_done' not in st.session_state:
                st.session_state.stream_analysis_done = False
            
            # 异步处理流式生成
            import asyncio
            async def handle_streaming():
                stream_generator = None
                try:
                    config = twitter_service.get_default_config(st.session_state.streaming_model)
                    stream_generator = twitter_service.generate_thread_enhanced_stream_async(
                        user_input=st.session_state.streaming_topic,
                        config=config,
                        personalization=st.session_state.streaming_personalization
                    )
                    
                    async for result in stream_generator:
                        if result["status"] == "progress":
                            # 进度更新
                            data = result.get("data", {})
                            if isinstance(data, dict):
                                stage = data.get("stage", "")
                                progress = data.get("progress", 0)
                                message = data.get("message", "")
                                
                                # 检查是否有推文数据
                                if "tweet_data" in data:
                                    tweet_data = data["tweet_data"]
                                    if isinstance(tweet_data, dict) and tweet_data.get("type") == "tweet":
                                        tweet_num = tweet_data.get("tweet_number", 0)
                                        
                                        # 添加新推文到session state
                                        if tweet_num not in st.session_state.stream_tweets:
                                            st.session_state.stream_tweets[tweet_num] = tweet_data
                                            
                                            # 更新流式容器显示 - 只显示新推文，避免重复
                                            with streaming_container:
                                                # 只在第一条推文时显示主题
                                                if len(st.session_state.stream_tweets) == 1 and st.session_state.stream_topic:
                                                    st.markdown(f"**主题：** {st.session_state.stream_topic}")
                                                    st.markdown("---")
                                                
                                                # 只显示当前新生成的推文
                                                tweet_content = tweet_data.get("tweet_content", "")
                                                
                                                with st.container(border=True):
                                                    st.markdown(f"**🐦 推文 {tweet_num}**")
                                                    st.markdown(tweet_content)
                                                    
                                                    # 显示字符数统计
                                                    char_count = count_twitter_chars(tweet_content)
                                                    if char_count > 280:
                                                        st.caption(f"⚠️ 字符数: {char_count}/280 (超出限制)")
                                                    else:
                                                        st.caption(f"✅ 字符数: {char_count}/280")
                                
                                # 检查是否有主题数据
                                elif "topic_data" in data:
                                    topic_data = data["topic_data"]
                                    if isinstance(topic_data, dict) and topic_data.get("type") == "topic":
                                        st.session_state.stream_topic = topic_data.get("topic", "")
                                
                                # 检查是否有最终结果
                                elif "final_outline" in data:
                                    outline = data["final_outline"]
                                    if outline:
                                        # 构建完整结果
                                        final_result = {
                                            "outline": outline,
                                            "outline_str": outline.display_outline() if hasattr(outline, 'display_outline') else ""
                                        }
                                        
                                        # 保存结果
                                        st.session_state.current_result = final_result
                                        st.session_state.generated_threads.append({
                                            "input_text": st.session_state.streaming_topic,
                                            "language": st.session_state.streaming_language,
                                            "personalization": st.session_state.streaming_personalization,
                                            "result": final_result
                                        })
                                        
                                        # 重置流式状态
                                        st.session_state.streaming_generation = False
                                        st.session_state.stream_tweets = {}
                                        st.session_state.stream_topic = ""
                                        st.session_state.stream_analysis_done = False
                                        st.session_state.display_mode = 'initial'
                                        st.session_state.generated_images = {}
                                        st.session_state.generating_image_for_tweet = None
                                        st.session_state.image_quality_settings = {}
                                        
                                        with progress_container:
                                            st.success("✅ 流式生成完成！")
                                        
                                        # 刷新页面显示最终结果
                                        st.rerun()
                                        return
                            
                                # 更新进度显示
                                with progress_container:
                                    if stage == "analysis":
                                        st.info(f"🔍 分析中... {progress}% - {message}")
                                    elif stage == "generation":
                                        st.info(f"🚀 生成中... {progress}% - {message}")
                                    else:
                                        st.info(f"⚡ 处理中... {progress}% - {message}")
                        
                        elif result["status"] == "node_update":
                            # 节点更新
                            node = result.get("node", "")
                            data = result.get("data", {})
                            
                            if node == "user_input_analysis" and isinstance(data, dict):
                                # 用户输入分析完成
                                analyzed_topic = data.get("topic", "")
                                current_language = data.get("language", "")
                                if analyzed_topic:
                                    st.session_state.stream_topic = analyzed_topic
                                st.session_state.stream_analysis_done = True
                                
                                # 更新进度显示
                                with progress_container:
                                    st.success(f"✅ 输入分析完成")
                                    if analyzed_topic:
                                        st.info(f"📋 主题: {analyzed_topic}")
                                    if current_language:
                                        st.info(f"🌍 语言: {current_language}")
                                    st.info("🔄 开始生成推文...")
                        
                        elif result["status"] == "raw_update":
                            # 原始数据更新 - 保留用于调试或其他原始数据
                            pass
                        
                        elif result["status"] == "error":
                            with progress_container:
                                st.error(f"❌ 生成失败: {result.get('error', '未知错误')}")
                            st.session_state.streaming_generation = False
                            st.session_state.stream_tweets = {}
                            st.session_state.stream_topic = ""
                            st.session_state.stream_analysis_done = False
                            break
                            
                except Exception as e:
                    with progress_container:
                        st.error(f"❌ 流式生成异常: {str(e)}")
                    st.session_state.streaming_generation = False
                    st.session_state.stream_tweets = {}
                    st.session_state.stream_topic = ""
                    st.session_state.stream_analysis_done = False
                finally:
                    # 确保异步生成器被正确关闭
                    if stream_generator is not None:
                        try:
                            await stream_generator.aclose()
                        except:
                            pass  # 忽略关闭异常
            
            # 运行异步函数
            try:
                twitter_service.safe_asyncio_run(handle_streaming())
            except Exception as e:
                st.error(f"❌ 异步处理异常: {str(e)}")
                st.session_state.streaming_generation = False
        
        elif st.session_state.current_result:
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
                
                # 添加图片生成功能说明
                with st.expander("🎨 图片生成功能说明"):
                    st.markdown("""
                    **如何为推文生成图片：**
                    1. 📝 生成完推文串后，每条推文右侧会显示"🎨 生成图片"按钮
                    2. 🎯 点击按钮前，可以选择图片质量等级（高质量需要更长时间）
                    3. 🖼️ 生成的图片会显示在推文下方，同时显示生成的提示词
                    4. ⏱️ 图片生成大约需要10-30秒，请耐心等待
                    
                    **图片质量说明：**
                    - 🔻 **低质量 (low)**: 快速生成，适合预览
                    - 🔸 **中等质量 (medium)**: 平衡速度和质量
                    - 🔺 **高质量 (high)**: 最佳视觉效果，生成时间较长
                    
                    **技术说明：**
                    - 使用OpenAI GPT-Image-1模型生成高质量图片
                    - AI会根据推文内容和整个推文串的上下文生成描述
                    - 图片尺寸为1024x1024，适合社交媒体使用
                    """)
                
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
                                    col_action1, col_action2 = st.columns(2)
                                    with col_action1:
                                        if st.button("✏️ 修改", key=f"modify_{leaf_node.tweet_number}", use_container_width=True):
                                            st.session_state.editing_tweet_number = leaf_node.tweet_number
                                            st.rerun()
                                    
                                    with col_action2:
                                        # 检查是否正在为这条tweet生成图片
                                        if st.session_state.generating_image_for_tweet == leaf_node.tweet_number:
                                            st.button("🎨 生成中...", key=f"generating_{leaf_node.tweet_number}", use_container_width=True, disabled=True)
                                        else:
                                            # 图片质量选择器
                                            current_quality = st.session_state.image_quality_settings.get(leaf_node.tweet_number, "medium")
                                            quality_options = ["low", "medium", "high"]
                                            quality_labels = {
                                                "low": "🔻 低质量 (快速)",
                                                "medium": "🔸 中等质量 (平衡)",
                                                "high": "🔺 高质量 (最佳)"
                                            }
                                            
                                            selected_quality = st.selectbox(
                                                "图片质量:",
                                                options=quality_options,
                                                index=quality_options.index(current_quality),
                                                format_func=lambda x: quality_labels[x],
                                                key=f"quality_select_{leaf_node.tweet_number}",
                                                help="选择图片生成质量。高质量需要更长生成时间，但视觉效果更佳。"
                                            )
                                            
                                            # 保存质量设置
                                            st.session_state.image_quality_settings[leaf_node.tweet_number] = selected_quality
                                            
                                            if st.button("🎨 生成图片", key=f"generate_image_{leaf_node.tweet_number}", use_container_width=True):
                                                # 构建tweet_thread（当前推文串的上下文）
                                                tweet_thread_context = []
                                                for node in outline.nodes:
                                                    for leaf in node.leaf_nodes:
                                                        tweet_thread_context.append(f"({leaf.tweet_number}) {leaf.tweet_content}")
                                                tweet_thread = "\n\n".join(tweet_thread_context)
                                                
                                                # 标记正在生成
                                                st.session_state.generating_image_for_tweet = leaf_node.tweet_number
                                                st.rerun()
                                
                                # 检查并显示图片生成状态
                                if st.session_state.generating_image_for_tweet == leaf_node.tweet_number:
                                    progress_text = st.empty()
                                    progress_text.info("🎨 步骤1: 分析推文内容，生成图片描述...")
                                    
                                    try:
                                        # 构建tweet_thread（当前推文串的上下文）
                                        tweet_thread_context = []
                                        for node in outline.nodes:
                                            for leaf in node.leaf_nodes:
                                                tweet_thread_context.append(f"({leaf.tweet_number}) {leaf.tweet_content}")
                                        tweet_thread = "\n\n".join(tweet_thread_context)
                                        
                                        progress_text.info("🎨 步骤2: 调用OpenAI生成图片...")
                                        
                                        # 获取用户选择的图片质量
                                        selected_image_quality = st.session_state.image_quality_settings.get(leaf_node.tweet_number, "medium")
                                        
                                        # 调用服务层生成图片
                                        image_result = twitter_service.generate_image(
                                            target_tweet=leaf_node.tweet_content,
                                            tweet_thread=tweet_thread,
                                            model=selected_model,
                                            image_quality=selected_image_quality
                                        )
                                        
                                        progress_text.empty()  # 清除进度信息
                                        
                                        # 处理结果
                                        if image_result["status"] == "success":
                                            image_data = image_result.get("data", {})
                                            image_url = image_data.get("image_url", "") if isinstance(image_data, dict) else ""
                                            image_prompt = image_data.get("image_prompt", "") if isinstance(image_data, dict) else ""
                                            
                                            if image_url:
                                                # 保存生成的图片信息，包括质量设置
                                                st.session_state.generated_images[leaf_node.tweet_number] = {
                                                    "url": image_url,
                                                    "prompt": image_prompt,
                                                    "quality": selected_image_quality
                                                }
                                                
                                                # 确认保存的数据
                                                saved_data = st.session_state.generated_images[leaf_node.tweet_number]
                                                st.write("💾 确认保存的数据:", {
                                                    "url_exists": bool(saved_data.get("url")),
                                                    "prompt_exists": bool(saved_data.get("prompt")),
                                                    "prompt_length": len(saved_data.get("prompt", ""))
                                                })
                                                
                                                st.success("✅ 图片生成成功！")
                                            else:
                                                st.error("❌ 图片生成失败: 未获取到图片URL")
                                        else:
                                            error_msg = image_result.get('error', '未知错误')
                                            st.error(f"❌ 图片生成失败: {error_msg}")
                                            # 显示详细错误信息
                                            with st.expander("🔍 查看详细错误信息"):
                                                st.text(str(image_result))
                                        
                                    except Exception as e:
                                        progress_text.empty()
                                        st.error(f"❌ 图片生成过程中发生异常: {str(e)}")
                                        with st.expander("🔍 查看异常详情"):
                                            st.text(str(e))
                                    
                                    # 清除生成状态
                                    st.session_state.generating_image_for_tweet = None
                                    st.rerun()

                                # 显示已生成的图片
                                if leaf_node.tweet_number in st.session_state.generated_images:
                                    image_info = st.session_state.generated_images[leaf_node.tweet_number]
                                    st.markdown("**🖼️ 生成的图片:**")
                                    try:
                                        st.image(image_info["url"], caption="AI生成的推文配图", use_container_width=True)
                                        
                                        # 显示图片生成提示词（添加调试信息）
                                        st.markdown("**🎯 图片生成提示词:**")
                                        prompt_value = image_info.get("prompt", "")
                                        
                                        # 调试信息
                                        if not prompt_value:
                                            st.warning("⚠️ 未获取到图片生成提示词")
                                            # 显示完整的image_info用于调试
                                            with st.expander("🔍 调试信息 - 查看图片信息"):
                                                st.json(image_info)
                                        else:
                                            st.text_area(
                                                label="",
                                                value=prompt_value,
                                                height=100,
                                                disabled=True,
                                                key=f"image_prompt_display_{leaf_node.tweet_number}",
                                                help="这是AI为当前推文生成的图片提示词"
                                            )
                                            
                                        # 总是显示图片信息的详细数据
                                        with st.expander("📊 图片详细信息"):
                                            st.write("**图片URL:**", image_info.get("url", "未知"))
                                            st.write("**图片质量:**", image_info.get("quality", "未知"))
                                            st.write("**提示词长度:**", len(prompt_value) if prompt_value else 0)
                                            if prompt_value:
                                                st.write("**提示词预览:**", prompt_value[:200] + "..." if len(prompt_value) > 200 else prompt_value)
                                    except Exception as e:
                                        st.error(f"图片显示失败: {str(e)}")
                                        # 移除无效的图片记录
                                        del st.session_state.generated_images[leaf_node.tweet_number]

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
                        if personalization.tweet_examples:
                            st.markdown(f"**例子：** {len(personalization.tweet_examples)} 条推文")
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